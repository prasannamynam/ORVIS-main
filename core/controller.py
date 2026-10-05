"""
core/controller.py

Coordinates:

    Camera
        ↓
    Detector
        ↓
    Individual Hand Recognition
        ↓
    Two-Hand Command Resolution
        ↓
    State
        ↓
    Mapping
        ↓
    Executor

This is the only module that knows about all
the other modules.
"""

from __future__ import annotations

from typing import Callable, Optional

from camera.camera import Camera

from execution.executor import (
    Executor,
    ExecutionError,
)

from gesture.recognizer import (
    GestureRecognizer,
)

from hand.detector import (
    HandDetector,
)

from mapping.manager import (
    MappingManager,
)

from core.state import (
    GestureState,
    RuntimeState,
)

from utils.constants import (
    ACTION_HOLD_HOTKEY,
    GESTURE_UNKNOWN,
)

from utils.logger import get_logger


log = get_logger(
    "core.controller"
)


# ---------------------------------------------------------------------------
# Callback
# ---------------------------------------------------------------------------

FrameCallback = Callable[
    [object, str, RuntimeState],
    None,
]


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class Controller:

    def __init__(
        self,
        camera: Optional[Camera] = None,
        detector: Optional[HandDetector] = None,
        recognizer: Optional[GestureRecognizer] = None,
        mapping_manager: Optional[MappingManager] = None,
        executor: Optional[Executor] = None,
    ):

        self.camera = (
            camera
            or Camera()
        )

        self.detector = detector

        self.recognizer = (
            recognizer
            or GestureRecognizer()
        )

        self.mapping_manager = (
            mapping_manager
            or MappingManager()
        )

        self.executor = (
            executor
            or Executor()
        )

        self.gesture_state = (
            GestureState()
        )

        self._active_hold_gesture: Optional[str] = None
        self._active_hold_signature: Optional[tuple[str, str, float]] = None

        self._running = False

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start(
        self,
        on_frame: Optional[
            FrameCallback
        ] = None,
    ) -> None:

        """
        Starts the camera and continuously processes frames.
        """

        # --------------------------------------------------------------
        # Create detector lazily
        # --------------------------------------------------------------

        if self.detector is None:

            self.detector = (
                HandDetector()
            )

        # --------------------------------------------------------------
        # Open camera
        # --------------------------------------------------------------

        self.camera.open()

        self._running = True

        log.info(
            "Controller started"
        )

        try:

            while self._running:

                # ------------------------------------------------------
                # Read frame
                # ------------------------------------------------------

                frame = (
                    self.camera.read_frame()
                )

                if frame is None:
                    continue

                # ------------------------------------------------------
                # Detect up to two hands
                # ------------------------------------------------------

                detection = (
                    self.detector.detect(
                        frame
                    )
                )

                # ------------------------------------------------------
                # Extract landmarks
                # ------------------------------------------------------

                hands = [
                    hand.landmarks
                    for hand
                    in detection.hands
                ]

                # ------------------------------------------------------
                # Resolve two-hand command
                # ------------------------------------------------------

                gesture = (
                    self.recognizer
                    .recognize_two_hands(
                        hands
                    )
                )

                # ------------------------------------------------------
                # Update execution state
                # ------------------------------------------------------

                state = self.process_gesture(gesture)

                # ------------------------------------------------------
                # GUI callback
                # ------------------------------------------------------

                if on_frame is not None:

                    display_frame = (
                        self.detector
                        .draw_landmarks(
                            frame,
                            detection,
                        )
                    )

                    on_frame(
                        display_frame,
                        gesture,
                        state,
                    )

        finally:

            self._release_active_hold_session()

            self.camera.release()

            log.info(
                "Controller stopped"
            )

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    def stop(self) -> None:

        self._running = False
        self._release_active_hold_session()

    # ------------------------------------------------------------------
    # Gesture Processing
    # ------------------------------------------------------------------

    def process_gesture(self, gesture: str) -> RuntimeState:
        """
        Process one recognized gesture and update execution state.

        Hold-hotkey actions are handled immediately and statefully here so
        they can keep modifier keys pressed across frames until the gesture
        disappears.
        """

        state = self.gesture_state.update(gesture)

        action_entry = self.mapping_manager.get_action(gesture)

        if self._active_hold_gesture is not None:
            hold_signature_matches = (
                action_entry is not None
                and action_entry.get("type") == ACTION_HOLD_HOTKEY
                and gesture == self._active_hold_gesture
                and self._active_hold_signature == self._hold_signature(action_entry)
            )

            if not hold_signature_matches:
                self._release_active_hold_session()

        if action_entry is not None and action_entry.get("type") == ACTION_HOLD_HOTKEY:
            self._process_hold_hotkey(gesture, action_entry)
            return state

        # UNKNOWN resets execution lock
        if gesture == GESTURE_UNKNOWN:
            self.gesture_state.reset_execution_lock()
            return state

        # Execute if stable
        if self.gesture_state.should_execute():
            self._try_execute(gesture)

        return state

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def _try_execute(
        self,
        gesture: str,
    ) -> None:

        # --------------------------------------------------------------
        # Find mapping
        # --------------------------------------------------------------

        action_entry = (
            self.mapping_manager
            .get_action(
                gesture
            )
        )

        # --------------------------------------------------------------
        # No mapping
        # --------------------------------------------------------------

        if action_entry is None:

            log.debug(
                "Gesture %s is stable "
                "but has no enabled mapping.",
                gesture,
            )

            # Prevent checking repeatedly
            # while gesture is held.
            self.gesture_state.\
                mark_executed()
            return

        # --------------------------------------------------------------
        # Execute mapped action
        # --------------------------------------------------------------

        try:

            self.executor.execute(
                action_entry
            )

        except ExecutionError as e:

            log.error(
                "Execution failed for "
                "gesture %s: %s",
                gesture,
                e,
            )

        finally:

            self.gesture_state.\
                mark_executed()

    # ------------------------------------------------------------------
    # Hold hotkey session
    # ------------------------------------------------------------------

    def _process_hold_hotkey(self, gesture: str, action_entry: dict) -> None:
        signature = self._hold_signature(action_entry)

        if self._active_hold_gesture != gesture or self._active_hold_signature != signature:
            self._release_active_hold_session()

            try:
                self.executor.start_hold_hotkey(action_entry)
            except ExecutionError as e:
                log.error(
                    "Failed to start hold hotkey for gesture %s: %s",
                    gesture,
                    e,
                )
                return

            self._active_hold_gesture = gesture
            self._active_hold_signature = signature
            return

        try:
            self.executor.repeat_hold_hotkey()
        except ExecutionError as e:
            log.error(
                "Failed to repeat hold hotkey for gesture %s: %s",
                gesture,
                e,
            )
            self._release_active_hold_session()

    def _release_active_hold_session(self) -> None:
        if self._active_hold_gesture is None:
            return

        try:
            self.executor.stop_active_sessions()
        finally:
            self._active_hold_gesture = None
            self._active_hold_signature = None

    @staticmethod
    def _hold_signature(action_entry: dict) -> tuple[str, str, float]:
        modifier = str(action_entry.get("modifier", "")).strip().lower()
        key = str(action_entry.get("key", "")).strip().lower()
        repeat_interval = float(action_entry.get("repeat_interval", 0.0) or 0.0)
        return modifier, key, repeat_interval

        # --------------------------------------------------------------
        # Execute mapped action
        # --------------------------------------------------------------

        try:

            self.executor.execute(
                action_entry
            )

        except ExecutionError as e:

            log.error(
                "Execution failed for "
                "gesture %s: %s",
                gesture,
                e,
            )

        finally:

            self.gesture_state.\
                mark_executed()
