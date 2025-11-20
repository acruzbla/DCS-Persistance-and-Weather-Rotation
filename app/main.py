# app/main.py
"""
Main module for the DCS persistence engine.

Handles:
1. Loading config.
2. Hour persistence (if enabled):
   - Extract mission time from DCS WebGUI.
   - Update mission start_time in the .miz.
3. Weather rotation (if enabled):
   - Kill DCS server.
   - Modify date and weather block in mission.
   - Repack .miz and restart DCS.

All errors:
- Logged in persistencia.log
- Notified to Discord (if enabled in config)
"""

import json
from pathlib import Path

from time_reader import extract_time_and_mission
from mission_time_updater import update_miz_start_time
from weather_rotator import rotate_weather_in_miz
from discord_notifier import notify_discord_error
from logger_setup import get_logger

logger = get_logger()

CONFIG_PATH = Path("../dcs_persistence_config.json")
RESULT_PATH = Path("extracted_time.json")


# -----------------------------------------------------
# CENTRAL FAIL HANDLER
# -----------------------------------------------------
def fail(reason: str):
    """
    HARD FAILURE:
    - Log reason
    - Notify Discord (if enabled)
    - Terminate execution immediately
    """
    logger.error(reason)

    try:
        notify_discord_error(reason)
    except Exception as e:
        logger.error(f"Failed to notify Discord: {e}")

    raise SystemExit(1)


# -----------------------------------------------------
# CONFIG LOADER
# -----------------------------------------------------
def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"Failed to load config: {e}")


# -----------------------------------------------------
# SAVE TIME RESULT (DEBUG / TRANSPARENCY)
# -----------------------------------------------------
def save_result(hms: str, seconds: int):
    try:
        RESULT_PATH.write_text(
            json.dumps(
                {"time_hms": hms, "time_seconds": seconds},
                indent=4
            ),
            encoding="utf-8",
        )
        logger.info(f"Saved extracted time into {RESULT_PATH}")
    except Exception as e:
        fail(f"Failed to save extracted time: {e}")


# -----------------------------------------------------
# MAIN LOGIC
# -----------------------------------------------------
def main():
    logger.info("==== Starting DCS Persistence Orchestrator ====")

    cfg = load_config()
    if not cfg:
        fail("Config is empty or invalid.")

    miz_path = cfg.get("mission_path", "")
    if not miz_path:
        fail("mission_path missing in config.")

    hour_enabled = cfg.get("hour_persistence_enabled", False)
    weather_enabled = cfg.get("weather_rotation_enabled", False)

    logger.info(f"Hour persistence enabled: {hour_enabled}")
    logger.info(f"Weather rotation enabled: {weather_enabled}")

    # If nothing is enabled, just exit clean
    if not hour_enabled and not weather_enabled:
        logger.info("Both hour persistence and weather rotation are disabled. Nothing to do. Exiting.")
        raise SystemExit(0)

    # ---------------------------------------------------------
    # 1) HOUR PERSISTENCE
    # ---------------------------------------------------------
    if hour_enabled:
        logger.info("---- Hour persistence process START ----")

        success, hms, seconds = extract_time_and_mission(miz_path)

        if not success:
            fail("Mission time extraction failed (mismatch or scraping error).")

        if hms is None or seconds is None:
            fail("Mission time not returned by extractor.")

        logger.info(f"Mission time extracted successfully: {hms} ({seconds} seconds)")
        save_result(hms, seconds)

        logger.info("Updating mission .miz start_time...")
        if not update_miz_start_time(miz_path, seconds):
            fail("Failed to update MIZ start_time.")

        logger.info("---- Hour persistence process DONE ----")

    else:
        logger.info("Hour persistence disabled in config. Skipping time extraction and .miz time update.")

    # ---------------------------------------------------------
    # 2) WEATHER ROTATION
    # ---------------------------------------------------------
    if weather_enabled:
        logger.info("---- Weather rotation process START ----")

        if not rotate_weather_in_miz():
            fail("Weather rotation failed.")

        logger.info("---- Weather rotation process DONE ----")

    else:
        logger.info("Weather rotation disabled in config. Skipping weather update.")

    # ---------------------------------------------------------
    # DONE
    # ---------------------------------------------------------
    logger.info("==== DCS Persistence Orchestrator COMPLETED SUCCESSFULLY ====")
    raise SystemExit(0)


# -----------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------
if __name__ == "__main__":
    main()
