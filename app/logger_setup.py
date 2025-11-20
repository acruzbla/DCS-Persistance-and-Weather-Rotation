# app/logger_setup.py
"""
Central logging setup.
All modules must import get_logger() to use the same file.
"""

import logging
from pathlib import Path

LOG_PATH = Path("persistencia.log")


def get_logger():
    logger = logging.getLogger("PERSISTENCIA")
    if not logger.handlers:

        logger.setLevel(logging.INFO)

        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"
        )
        fh.setFormatter(formatter)

        logger.addHandler(fh)

    return logger
