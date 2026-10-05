"""
camera/camera.py

Responsible ONLY for:
- Opening the webcam
- Capturing frames
- Returning frames
- Releasing the webcam
- Closing OpenCV windows

Knows nothing about hands, gestures, or actions.
"""

from __future__ import annotations

import cv2

from utils.logger import get_logger

log = get_logger("camera")


class CameraError(RuntimeError):
    """Raised when the webcam cannot be opened or read from."""


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480):
        self.index = index
        self.width = width
        self.height = height
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        log.info("Opening camera index=%s", self.index)
        self._cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW) if _is_windows() else cv2.VideoCapture(self.index)

        if self.width:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        if not self._cap.isOpened():
            raise CameraError(f"Could not open webcam at index {self.index}")

        log.info("Camera opened successfully")

    def read_frame(self):
        """Returns a BGR frame (numpy array) or None if the read failed."""
        if self._cap is None:
            raise CameraError("Camera not opened. Call open() first.")

        ok, frame = self._cap.read()
        if not ok:
            log.warning("Failed to read frame from camera")
            return None
        return frame

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            log.info("Camera released")

    def __enter__(self) -> "Camera":
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()


def _is_windows() -> bool:
    import platform
    return platform.system().lower() == "windows"


def close_windows() -> None:
    cv2.destroyAllWindows()
