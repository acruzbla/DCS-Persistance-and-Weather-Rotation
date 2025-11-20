# app/weather_rotator.py
"""
Dynamic weather rotation module.

Process:
0. Applies ONLY if weather_rotation_enabled == true in config.
1. If DCS_server.exe is running -> stop it (info, not warning).
2. Extract "mission" file from .miz using 7zip.
3. Update the date block depending on configured season.
4. Choose a random weather template (.config) from:
   - app/weather/bad_weather
   - app/weather/good_weather
   based on weather_bad_weather_percentage.
5. Replace the ["weather"] = {...} block with the template content.
6. Repack "mission" into the .miz.
7. Restart DCS_server.exe.
"""

import json
import random
import re
import subprocess
import tempfile
import time
from datetime import date
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

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "dcs_persistence_config.json"

SEVEN_ZIP_PATH = r"C:\Program Files\7-Zip\7z.exe"
DCS_SERVER_EXE = r"C:\Program Files\Eagle Dynamics\DCS World Server\bin\DCS_server.exe"

WEATHER_ROOT = BASE_DIR / "weather"
BAD_WEATHER_DIR = WEATHER_ROOT / "bad_weather"
GOOD_WEATHER_DIR = WEATHER_ROOT / "good_weather"


# ---------------- FAIL HELPERS ----------------

def fail_local(reason: str) -> bool:
    """
    Local failure:
    - Log
    - Notify Discord (error)
    - Return False
    """
    logger.error(reason)
    try:
        notify_discord_error(reason)
    except Exception as e:
        logger.error(f"[Weather] Failed to notify Discord: {e}")
    return False


# ---------------- PROCESS MANAGEMENT ----------------

def _kill_dcs_server_if_running() -> bool:
    """
    If DCS_server.exe is running:
    - Log info
    - Notify Discord info (not warning)
    - Kill the process
    - Wait 15 seconds

    If not running, log and continue.
    """
    logger.info("[Weather] Checking if DCS_server.exe is running...")

    for proc in psutil.process_iter(attrs=['pid', 'name']):
        name = proc.info.get("name") or ""
        if "DCS_server.exe" in name:
            pid = proc.info["pid"]
            logger.info(f"[Weather] DCS_server.exe detected (PID {pid}). Stopping it to update weather...")

            try:
                notify_discord_info("DCS server stopped to apply dynamic weather rotation.")
            except Exception as e:
                logger.error(f"[Weather] Failed to send Discord info about DCS stop: {e}")

            try:
                psutil.Process(pid).kill()
                logger.info("[Weather] DCS_server.exe stopped successfully. Waiting 15 seconds...")
                time.sleep(15)
                return True
            except Exception as e:
                return fail_local(f"[Weather] Failed to stop DCS_server.exe: {e}")

    logger.info("[Weather] DCS_server.exe is not running. Continuing normally.")
    return True


def _start_dcs_server() -> bool:
    """
    Start DCS_server.exe after updating mission/weather.
    """
    logger.info(f"[Weather] Starting DCS server: {DCS_SERVER_EXE}")

    try:
        subprocess.Popen(
            [DCS_SERVER_EXE],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("[Weather] DCS_server.exe started successfully.")
        try:
            notify_discord_info("DCS server restarted successfully after weather rotation.")
        except Exception as e:
            logger.error(f"[Weather] Failed to send Discord info about DCS restart: {e}")
        return True

    except Exception as e:
        msg = f"[Weather] Failed to start DCS_server.exe: {e}"
        logger.error(msg)
        try:
            notify_discord_error(msg)
        except Exception as e2:
            logger.error(f"[Weather] Failed to notify Discord about DCS start error: {e2}")
        return False


# ---------------- 7ZIP UTILS ----------------

def _run_7zip(args: list) -> bool:
    cmd = [SEVEN_ZIP_PATH] + args
    logger.info(f"[Weather] Running 7zip: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        error_msg = f"[Weather] 7zip error: {result.stderr}"
        logger.error(error_msg)
        try:
            notify_discord_error(error_msg)
        except Exception as e:
            logger.error(f"[Weather] Failed to notify Discord about 7zip error: {e}")
        return False

    return True


# ---------------- DATE BLOCK ----------------

def _build_date_for_season(season: str) -> tuple[int, int, int]:
    """
    Returns (year, month, day) for the selected season.
    If realistic -> today.
    Else fixed 2025 dates as requested.
    """
    if season == "realistic":
        today = date.today()
        return today.year, today.month, today.day

    mapping = {
        "summer": (2025, 8, 1),   # 1 August 2025
        "winter": (2025, 2, 1),   # 1 February 2025
        "autumn": (2025, 10, 1),  # 1 October 2025
        "spring": (2025, 5, 1),   # 1 May 2025
    }

    return mapping.get(season, (2025, 9, 1))  # fallback: 1 September 2025


def _update_date_block(text: str, season: str) -> Optional[str]:
    """
    Replace the ["date"] block with a new one matching the given season.

    Soporta:
    - Orden de campos variable (Year/Day/Month o Day/Year/Month, etc.)
    - Con o sin comentario final: -- end of ["date"]
    - Distintos espacios/tabulaciones
    """
    year, month, day = _build_date_for_season(season)
    logger.info(f"[Weather] Setting mission date for season '{season}': {day}-{month}-{year}")

    new_block = (
        '\t["date"] = \n'
        '\t{\n'
        f'\t\t["Day"] = {day},\n'
        f'\t\t["Year"] = {year},\n'
        f'\t\t["Month"] = {month},\n'
        '\t}, -- end of ["date"]\n'
    )

    # Regex más flexible para el bloque date:
    # - No depende del orden interno de las líneas.
    # - Captura todo entre { ... }, hasta la primera '},'
    # - Acepta (o no) el comentario '-- end of ["date"]'
    pattern = re.compile(
        r'\s*\["date"\]\s*=\s*\{.*?\},\s*(?:--\s*end of \["date"\])?',
        re.DOTALL,
    )

    if not pattern.search(text):
        logger.error("[Weather] Could not find date block in mission.")
        return None

    new_text = pattern.sub(new_block, text, count=1)
    return new_text


# ---------------- WEATHER BLOCK ----------------

def _pick_weather_template(bad_percentage: int) -> Optional[str]:
    """
    Chooses a weather template file from bad_weather or good_weather
    based on bad_percentage (0-100). Returns file content as string.
    """
    if bad_percentage < 0:
        bad_percentage = 0
    if bad_percentage > 100:
        bad_percentage = 100

    roll = random.randint(1, 100)
    logger.info(f"[Weather] Bad weather percentage: {bad_percentage}%. Roll: {roll}")

    if roll <= bad_percentage:
        chosen_dir = BAD_WEATHER_DIR
        logger.info("[Weather] Selecting BAD weather template.")
    else:
        chosen_dir = GOOD_WEATHER_DIR
        logger.info("[Weather] Selecting GOOD weather template.")

    if not chosen_dir.exists():
        return None

    candidates = list(chosen_dir.glob("*.config"))
    if not candidates:
        logger.error(f"[Weather] No .config files found in {chosen_dir}")
        return None

    template_path = random.choice(candidates)
    logger.info(f"[Weather] Selected weather template: {template_path}")

    try:
        return template_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.error(f"[Weather] Failed to read weather template {template_path}: {e}")
        return None


def _replace_weather_block(text: str, new_weather_block: str) -> Optional[str]:
    """
    Replace the ["weather"] = {...} block with new_weather_block.
    Assumes new_weather_block contains the full block including '["weather"] = { ... }'
    and the '-- end of ["weather"]' comment.
    """
    pattern = re.compile(
        r'\["weather"\]\s*=\s*\{.*?\},\s*-- end of \["weather"\]',
        re.DOTALL,
    )

    if not pattern.search(text):
        logger.error("[Weather] Could not find weather block in mission.")
        return None

    new_text = pattern.sub(new_weather_block, text, count=1)
    return new_text


# ---------------- PUBLIC ENTRYPOINT ----------------

def rotate_weather_in_miz() -> bool:
    """
    Main entrypoint for dynamic weather:
    - Reads config
    - Skips if weather_rotation_enabled is false
    - Applies date + weather changes if enabled
    """

    # Load config
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        return fail_local(f"[Weather] Failed to load config: {e}")

    if not cfg:
        return fail_local("[Weather] Config is empty or invalid.")

    if not cfg.get("weather_rotation_enabled", False):
        logger.info("[Weather] Weather rotation disabled in config. Skipping and exiting.")
        return True  # no-op, but considered success

    miz_path = cfg.get("mission_path", "")
    if not miz_path:
        return fail_local("[Weather] mission_path missing in config.")

    season = cfg.get("weather_season", "realistic")
    bad_pct = int(cfg.get("weather_bad_weather_percentage", 0))

    miz = Path(miz_path)
    if not miz.exists():
        return fail_local(f"[Weather] MIZ file not found: {miz}")

    logger.info("[Weather] ==== Starting dynamic weather rotation ====")
    logger.info(f"[Weather] Mission file: {miz}")
    logger.info(f"[Weather] Season: {season}")
    logger.info(f"[Weather] Bad weather percentage: {bad_pct}%")

    # STEP 1 — Kill DCS server if running
    if not _kill_dcs_server_if_running():
        return False

    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)
        mission_path = tempdir / "mission"

        # STEP 2 — Extract "mission" from miz
        if not _run_7zip(["e", str(miz), "mission", f"-o{tempdir}", "-y"]):
            return fail_local("[Weather] Failed to extract 'mission' from .miz.")

        if not mission_path.exists():
            return fail_local("[Weather] 'mission' file missing after extraction.")

        try:
            text = mission_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            return fail_local(f"[Weather] Failed reading mission file: {e}")

        # STEP 3 — Update date block
        new_text = _update_date_block(text, season)
        if new_text is None:
            return fail_local("[Weather] Failed to update date block.")
        text = new_text

        # STEP 4 — Choose weather template
        template = _pick_weather_template(bad_pct)
        if template is None:
            return fail_local("[Weather] Failed to choose weather template.")

        # STEP 5 — Replace weather block
        replaced = _replace_weather_block(text, template)
        if replaced is None:
            return fail_local("[Weather] Failed to replace weather block in mission.")
        text = replaced

        # STEP 6 — Save updated mission
        try:
            mission_path.write_text(text, encoding="utf-8")
        except Exception as e:
            return fail_local(f"[Weather] Failed writing updated mission file: {e}")

        # STEP 7 — Update .miz archive
        if not _run_7zip(["u", str(miz), str(mission_path), "-y"]):
            return fail_local("[Weather] Failed to update mission inside .miz.")

    # STEP 8 — Restart DCS server
    if not _start_dcs_server():
        return False

    logger.info("[Weather] Dynamic weather rotation completed and DCS server restarted.")
    return True
