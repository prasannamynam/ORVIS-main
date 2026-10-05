"""
main.py

ORVIX — Vision-Based Hand Gesture Desktop Automation System.

Entry point: starts the Tkinter GUI, which owns camera start/stop and the
mapping table. All heavy lifting is delegated to the core.Controller and
the individual modules it coordinates.
"""

from gui.app import main
from utils.logger import get_logger

log = get_logger("main")

if __name__ == "__main__":
    log.info("Starting ORVIX")
    main()