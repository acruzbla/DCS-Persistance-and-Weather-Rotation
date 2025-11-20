# app/time_reader.py
"""
Full time extractor for DCS WebGUI.
Sequence:
1. Wait for "Server detected"
2. Click CONNECT
3. Wait for dashboard to load
4. Validate mission path (normalized)
5. Extract mission time and convert to seconds
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from logger_setup import get_logger

logger = get_logger()


WEBGUI_URL = r"file:///C:/Program Files/Eagle Dynamics/DCS World Server/WebGUI/index.html"

# ------------------ CSS SELECTORS ------------------

CSS_SERVER_DETECTED = (
    "body > div > div > div.v--modal-overlay > div > "
    "div.v--modal-box.v--modal > div.content.scroll-y > "
    "div.server-status > div"
)

CSS_CONNECT_BUTTON = (
    "body > div > div > div.v--modal-overlay > div > "
    "div.v--modal-box.v--modal > div.footer > div > button"
)

CSS_MISSION_FILENAME = (
    "body > div > div > div.container-fluid > div.row > div > div > "
    "div > div > div > div.missions-list > div > div.card-body.p-0 > "
    "div > div > span > div > div > div.col-sm-6.col-md-7.col-5 > div"
)

CSS_MISSION_TIME = (
    "body > div > div > div.container-fluid > div.row > div > div > "
    "div > div > div > div.card.server-settings.mb-3 > div > div > "
    "div:nth-child(2) > div > p:nth-child(6) > span"
)


# ------------------ HELPERS ------------------

def _convert_hms_to_seconds(hms: str) -> int:
    try:
        h, m, s = hms.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except Exception:
        return 0


def _normalize_path(p: str) -> str:
    """Unify path format so DCS and config always match."""
    return (
        p.replace("\\", "/")
         .replace("//", "/")
         .lower()
         .strip()
    )


# ------------------ MAIN FUNCTION ------------------

def extract_time_and_mission(expected_miz_path: str):
    logger.info("Starting DCS WebGUI mission time extraction...")

    chrome_opts = Options()
    chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--no-sandbox")

    driver = None

    try:
        driver = webdriver.Chrome(options=chrome_opts)
        driver.get(WEBGUI_URL)

        wait = WebDriverWait(driver, 40)

        # ------------------------------------------------------
        # STEP 1: WAIT FOR "SERVER DETECTED"
        # ------------------------------------------------------
        logger.info("Waiting for 'Server detected' popup...")

        server_detected_elem = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_SERVER_DETECTED))
        )

        text = server_detected_elem.text.strip()
        if "server detected" not in text.lower():
            logger.error(f"Unexpected server detected text: {text}")
            return False, None, None

        logger.info("Server detected!")

        # ------------------------------------------------------
        # STEP 2: CLICK CONNECT
        # ------------------------------------------------------
        logger.info("Clicking CONNECT button...")

        connect_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, CSS_CONNECT_BUTTON))
        )
        connect_btn.click()

        # ------------------------------------------------------
        # STEP 3: WAIT FOR DASHBOARD (20s FIXED)
        # ------------------------------------------------------
        logger.info("Waiting 20 seconds for dashboard to load...")
        time.sleep(20)

        # ------------------------------------------------------
        # STEP 4: GET MISSION FILENAME
        # ------------------------------------------------------
        logger.info("Extracting mission filename from dashboard...")

        mission_elem = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_MISSION_FILENAME))
        )

        loaded_miz = mission_elem.text.strip()
        logger.info(f"Loaded mission: {loaded_miz}")

        # Normalize both paths
        loaded_norm = _normalize_path(loaded_miz)
        expected_norm = _normalize_path(expected_miz_path)

        logger.info(f"Normalized loaded:   {loaded_norm}")
        logger.info(f"Normalized expected: {expected_norm}")

        if loaded_norm != expected_norm:
            logger.warning(
                f"MISSION MISMATCH → Expected: {expected_norm} | Found: {loaded_norm}"
            )
            return False, None, None

        # ------------------------------------------------------
        # STEP 5: GET MISSION TIME
        # ------------------------------------------------------
        logger.info("Extracting mission time...")

        time_elem = wait.until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, CSS_MISSION_TIME))
        )

        mission_time = time_elem.text.strip()
        seconds = _convert_hms_to_seconds(mission_time)

        logger.info(f"Mission time extracted: {mission_time} ({seconds} seconds)")

        return True, mission_time, seconds

    except Exception as e:
        logger.exception(f"Time extraction ERROR: {e}")
        return False, None, None

    finally:
        if driver:
            driver.quit()
