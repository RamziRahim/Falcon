"""
Common logging utilities for Swing Trading Platform
"""

import logging
import os
from datetime import datetime
from config import LOG_FOLDER

os.makedirs(LOG_FOLDER, exist_ok=True)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )

    logfile = os.path.join(
        LOG_FOLDER,
        f"{name}_{datetime.now().strftime('%Y%m%d')}.log"
    )

    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger


class Timer:
    def __init__(self):
        self.start = datetime.now()

    def elapsed(self):
        return datetime.now() - self.start


def log_summary(logger, processed=0, success=0, failed=0, skipped=0, timer=None):
    logger.info("=" * 60)
    logger.info("EXECUTION SUMMARY")
    logger.info("Processed : %s", processed)
    logger.info("Success   : %s", success)
    logger.info("Failed    : %s", failed)
    logger.info("Skipped   : %s", skipped)
    if timer:
        logger.info("Runtime   : %s", timer.elapsed())
    logger.info("=" * 60)
