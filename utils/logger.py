"""
Central logger for ORVIX.

Usage:
    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("message")
"""

import logging
from logging.handlers import RotatingFileHandler

from utils.constants import LOG_PATH

_CONFIGURED = False


def _configure_root() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger("orvix")
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    # Rotating file handler (keeps logs from growing forever)
    try:
        file_handler = RotatingFileHandler(
            LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError:
        # If the log file can't be created (e.g. read-only dir), fall back
        # to console-only logging rather than crashing the app.
        root.warning("Could not create log file at %s; logging to console only.", LOG_PATH)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure_root()
    return logging.getLogger(f"orvix.{name}")
