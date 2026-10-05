"""
hand/detector.py

Responsible for:

- Loading MediaPipe Hand Landmarker
- Detecting up to two hands
- Returning landmarks for every detected hand
- Returning handedness information
- Drawing all detected hands on the camera frame

Uses MediaPipe Tasks API.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import cv2
import mediapipe as mp

from mediapipe.tasks.python import BaseOptions

from mediapipe.tasks.python.vision import (
    HandLandmarker,
    HandLandmarkerOptions,
    RunningMode,
)

from utils.constants import (
    MAX_NUM_HANDS,
    MIN_HAND_DETECTION_CONFIDENCE,
    MIN_HAND_PRESENCE_CONFIDENCE,
    MIN_TRACKING_CONFIDENCE,
    MODEL_PATH,
)

from utils.logger import get_logger


log = get_logger("hand.detector")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DetectedHand:
    """
    Represents one detected hand.
    """

    landmarks: List[List[float]]
    handedness: Optional[str]


@dataclass
class HandDetectionResult:
    """
    Result of detecting hands in one frame.

    hands can contain:

        []
        [hand]
        [hand, hand]
    """

    hands: List[DetectedHand]


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class HandDetector:
    """
    Thin wrapper around MediaPipe HandLandmarker.

    Supports up to two hands.
    """

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        max_hands: int = MAX_NUM_HANDS,
    ):
        self.model_path = Path(model_path)
        self.max_hands = max_hands

        self._landmarker: Optional[HandLandmarker] = None

        self._start_time_ms = int(
            time.time() * 1000
        )

        self._validate_model_file()
        self._load_landmarker()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _validate_model_file(self) -> None:

        if not self.model_path.exists():
            raise FileNotFoundError(
                "Hand Landmarker model not found at:\n"
                f"    {self.model_path}\n\n"
                "Download 'hand_landmarker.task' and place it "
                "at that exact path."
            )

        if self.model_path.stat().st_size == 0:
            raise FileNotFoundError(
                f"Hand Landmarker model file at "
                f"{self.model_path} is empty (0 bytes)."
            )

    def _load_landmarker(self) -> None:

        log.info(
            "Loading HandLandmarker model from %s",
            self.model_path,
        )

        options = HandLandmarkerOptions(
            base_options=BaseOptions(
                model_asset_path=str(self.model_path)
            ),
            running_mode=RunningMode.VIDEO,

            # IMPORTANT:
            # Detect two hands.
            num_hands=self.max_hands,

            min_hand_detection_confidence=(
                MIN_HAND_DETECTION_CONFIDENCE
            ),

            min_hand_presence_confidence=(
                MIN_HAND_PRESENCE_CONFIDENCE
            ),

            min_tracking_confidence=(
                MIN_TRACKING_CONFIDENCE
            ),
        )

        self._landmarker = (
            HandLandmarker.create_from_options(options)
        )

        log.info(
            "HandLandmarker loaded successfully"
        )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect(self, bgr_frame) -> HandDetectionResult:
        """
        Detect up to two hands from an OpenCV BGR frame.

        Returns:
            HandDetectionResult
        """

        if self._landmarker is None:
            raise RuntimeError(
                "HandDetector is closed."
            )

        # --------------------------------------------------------------
        # BGR -> RGB
        # --------------------------------------------------------------

        rgb_frame = cv2.cvtColor(
            bgr_frame,
            cv2.COLOR_BGR2RGB,
        )

        # --------------------------------------------------------------
        # OpenCV frame -> MediaPipe Image
        # --------------------------------------------------------------

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame,
        )

        # --------------------------------------------------------------
        # Timestamp
        # --------------------------------------------------------------

        timestamp_ms = (
            int(time.time() * 1000)
            - self._start_time_ms
        )

        # --------------------------------------------------------------
        # MediaPipe detection
        # --------------------------------------------------------------

        result = self._landmarker.detect_for_video(
            mp_image,
            timestamp_ms,
        )

        # --------------------------------------------------------------
        # No hands
        # --------------------------------------------------------------

        if not result.hand_landmarks:

            return HandDetectionResult(
                hands=[]
            )

        # --------------------------------------------------------------
        # Extract every detected hand
        # --------------------------------------------------------------

        detected_hands: List[DetectedHand] = []

        for index, hand_landmarks in enumerate(
            result.hand_landmarks
        ):

            landmarks = [
                [
                    landmark.x,
                    landmark.y,
                    landmark.z,
                ]
                for landmark in hand_landmarks
            ]

            handedness = None

            if (
                result.handedness
                and index < len(result.handedness)
                and result.handedness[index]
            ):
                handedness = (
                    result.handedness[index][0]
                    .category_name
                )

            detected_hands.append(
                DetectedHand(
                    landmarks=landmarks,
                    handedness=handedness,
                )
            )

        log.debug(
            "Detected %d hand(s)",
            len(detected_hands),
        )

        return HandDetectionResult(
            hands=detected_hands
        )

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    @staticmethod
    def draw_landmarks(
        bgr_frame,
        detection: HandDetectionResult,
    ):
        """
        Draw landmarks for all detected hands.
        """

        frame = bgr_frame.copy()

        h, w = frame.shape[:2]

        connections = [
            # Thumb
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 4),

            # Index
            (0, 5),
            (5, 6),
            (6, 7),
            (7, 8),

            # Middle
            (0, 9),
            (9, 10),
            (10, 11),
            (11, 12),

            # Ring
            (0, 13),
            (13, 14),
            (14, 15),
            (15, 16),

            # Little
            (0, 17),
            (17, 18),
            (18, 19),
            (19, 20),

            # Palm
            (5, 9),
            (9, 13),
            (13, 17),
        ]

        # --------------------------------------------------------------
        # Draw every detected hand
        # --------------------------------------------------------------

        for hand in detection.hands:

            points = [
                (
                    int(x * w),
                    int(y * h),
                )
                for x, y, _ in hand.landmarks
            ]

            # Bones
            for a, b in connections:

                cv2.line(
                    frame,
                    points[a],
                    points[b],
                    (0, 255, 0),
                    2,
                )

            # Landmark points
            for x, y in points:

                cv2.circle(
                    frame,
                    (x, y),
                    4,
                    (0, 0, 255),
                    -1,
                )

        return frame

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def close(self) -> None:

        if self._landmarker is not None:

            self._landmarker.close()

            self._landmarker = None

            log.info(
                "HandLandmarker closed"
            )

    def __enter__(self) -> "HandDetector":
        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ) -> None:

        self.close()