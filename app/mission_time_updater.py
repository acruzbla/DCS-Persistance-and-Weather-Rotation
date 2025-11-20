# app/mission_time_updater.py
"""
Module to update mission start_time inside a .miz file.
Process:
1. Kill DCS_server.exe if running
2. Extract "mission" file from .miz using 7zip
3. Find LAST ["start_time"] = X,
4. Add extracted seconds (with wrap at 86399)
5. Replace ONLY the last occurrence
6. Re-insert "mission" into the .miz using 7zip
7. Restart DCS_server.exe
"""

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import psutil

from logger_setup import get_logger
from discord_notifier import (
    notify_discord_error,
    notify_discord_info,
)

logger = get_logger()

# ---------------- CONFIG ----------------
SEVEN_ZIP_PATH = r"C:\Program Files\7-Zip\7z.exe"  # Adjust if needed
DCS_SERVER_EXE = r"C:\Program Files\Eagle Dynamics\DCS World Server\bin\DCS_server.exe"
MAX_TIME = 86399  # Last second in 24h


# ---------------- INTERNAL FAIL ----------------

def fail_local(reason: str) -> bool:
    """
    Local failure:
    - Log
    - Notify Discord (error)
    - Return False to caller
    """
    logger.error(reason)
    try:
        notify_discord_error(reason)
    except Exception as e:
        logger.error(f"Discord notify failed inside mission_time_updater: {e}")
    return False


# ---------------- PROCESS MANAGEMENT ----------------

def _kill_dcs_server_if_running() -> bool:
    """
    If DCS_server.exe is running:
    - Log info
    - Send info notification to Discord
    - Kill it
    - Wait 15 seconds

    If not running, just log and continue.
    """
    logger.info("Checking if DCS_server.exe is running...")

    for proc in psutil.process_iter(attrs=['pid', 'name']):
        name = proc.info.get("name") or ""
        if "DCS_server.exe" in name:
            pid = proc.info["pid"]
            logger.info(f"DCS_server.exe detected (PID {pid}). Stopping it to update mission...")

            try:
                notify_discord_info("DCS server stopped to apply mission time update.")
            except Exception as e:
                logger.error(f"Failed to send Discord info about DCS stop: {e}")

            try:
                psutil.Process(pid).kill()
                logger.info("DCS_server.exe stopped successfully. Waiting 15 seconds before mission update...")
                time.sleep(15)
                return True
            except Exception as e:
                return fail_local(f"Failed to stop DCS_server.exe: {e}")

    logger.info("DCS_server.exe is not running. Continuing normally.")
    return True


def _start_dcs_server() -> bool:
    """
    Start DCS_server.exe after updating the mission.
    """
    logger.info(f"Starting DCS server: {DCS_SERVER_EXE}")

    try:
        subprocess.Popen(
            [DCS_SERVER_EXE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("DCS_server.exe started successfully.")
        try:
            notify_discord_info("DCS server restarted successfully after mission update.")
        except Exception as e:
            logger.error(f"Failed to send Discord info about DCS restart: {e}")
        return True

    except Exception as e:
        msg = f"Failed to start DCS_server.exe: {e}"
        logger.error(msg)
        try:
            notify_discord_error(msg)
        except Exception as e2:
            logger.error(f"Failed to notify Discord about DCS start error: {e2}")
        return False


# ---------------- INTERNAL UTILS ----------------

def _run_7zip(args: list) -> bool:
    cmd = [SEVEN_ZIP_PATH] + args
    logger.info(f"Running 7zip: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        error_msg = f"7zip error: {result.stderr}"
        logger.error(error_msg)
        try:
            notify_discord_error(error_msg)
        except Exception as e:
            logger.error(f"Failed to notify Discord about 7zip error: {e}")
        return False

    return True


def _parse_start_time(text: str) -> Optional[int]:
    """
    Return the LAST occurrence of ["start_time"] = X,
    Mission files often contain several, only the last one matters.
    """
    last_value: Optional[int] = None

    for line in text.splitlines():
        if '"start_time"' in line or '["start_time"]' in line:
            try:
                cleaned = line.strip()
                number = cleaned.split("=")[1].split(",")[0].strip()
                last_value = int(number)
            except Exception:
                pass

    return last_value


def _replace_start_time(text: str, new_value: int) -> str:
    """
    Replace ONLY the last occurrence of ["start_time"].
    """
    lines = text.splitlines()
    last_index: Optional[int] = None

    for i, line in enumerate(lines):
        if '"start_time"' in line or '["start_time"]' in line:
            last_index = i

    if last_index is None:
        return text

    lines[last_index] = f'\t["start_time"] = {new_value},'
    return "\n".join(lines)


# ---------------- PUBLIC FUNCTION ----------------

def update_miz_start_time(miz_path: str, seconds_to_add: int) -> bool:
    """
    Updates the mission start_time by adding seconds_to_add, with wrap at 86399,
    and restarts the DCS server afterwards.
    """
    miz = Path(miz_path)

    if not miz.exists():
        return fail_local(f"MIZ file not found: {miz}")

    logger.info(f"Preparing to update MIZ: {miz}")
    logger.info(f"Seconds to add to start_time: {seconds_to_add}")

    # STEP 1 — Kill DCS server if running
    if not _kill_dcs_server_if_running():
        return False

    # STEP 2 — Work in a temp directory
    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)
        mission_path = tempdir / "mission"

        # Extract "mission"
        if not _run_7zip(["e", str(miz), "mission", f"-o{tempdir}", "-y"]):
            return fail_local("Failed to extract 'mission' from .miz.")

        if not mission_path.exists():
            return fail_local("'mission' file missing after extraction.")

        # Read mission
        try:
            text = mission_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return fail_local(f"Failed reading mission file: {e}")

        current_start = _parse_start_time(text)
        if current_start is None:
            return fail_local("No start_time found inside mission file.")

        logger.info(f"Original start_time (last occurrence): {current_start}")

        # Compute new wrapped time
        new_time = (current_start + seconds_to_add) % (MAX_TIME + 1)
        logger.info(f"New start_time: {new_time}")

        # Replace last start_time
        new_text = _replace_start_time(text, new_time)

        try:
            mission_path.write_text(new_text, encoding="utf-8")
        except Exception as e:
            return fail_local(f"Failed writing updated mission file: {e}")

        # Update the .miz archive
        if not _run_7zip(["u", str(miz), str(mission_path), "-y"]):
            return fail_local("Failed to update mission inside .miz.")

    # STEP 3 — Restart DCS server
    if not _start_dcs_server():
        return False

    logger.info("Mission start_time updated and DCS server restarted successfully.")
    return True
