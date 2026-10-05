"""
core/state.py

Responsible for runtime state:
- Current gesture
- Previous gesture
- Gesture stability tracking
- Cooldown tracking
- Last executed gesture
- Overall detection state (state machine)

State machine:

    UNKNOWN -> GESTURE_DETECTED -> GESTURE_STABLE -> ACTION_EXECUTED -> COOLDOWN -> WAITING -> UNKNOWN
"""

from __future__ import annotations

import time
from enum import Enum, auto
from typing import Optional

from utils.constants import COOLDOWN_SECONDS, GESTURE_STABILITY_SECONDS, GESTURE_UNKNOWN
from utils.logger import get_logger

log = get_logger("core.state")


class RuntimeState(Enum):
    UNKNOWN = auto()
    GESTURE_DETECTED = auto()
    GESTURE_STABLE = auto()
    ACTION_EXECUTED = auto()
    COOLDOWN = auto()
    WAITING = auto()


class GestureState:
    """
    Tracks the current gesture over time and decides when it has become
    "stable" (held long enough to trust) and when it's safe to execute
    again after a cooldown. This is what prevents a single gesture from
    firing its action dozens of times per second.
    """

    def __init__(
        self,
        stability_seconds: float = GESTURE_STABILITY_SECONDS,
        cooldown_seconds: float = COOLDOWN_SECONDS,
    ):
        self.stability_seconds = stability_seconds
        self.cooldown_seconds = cooldown_seconds

        self.state: RuntimeState = RuntimeState.UNKNOWN
        self.current_gesture: str = GESTURE_UNKNOWN
        self.previous_gesture: str = GESTURE_UNKNOWN
        self.last_executed_gesture: Optional[str] = None

        self._gesture_start_time: Optional[float] = None
        self._cooldown_until: float = 0.0

    def update(self, detected_gesture: str) -> RuntimeState:
        """
        Feed the latest recognized gesture in. Returns the resulting
        RuntimeState for this frame. Call `should_execute()` afterwards
        to know whether the controller should fire an action.
        """
        now = time.monotonic()

        # Still cooling down from the last execution.
        if now < self._cooldown_until:
            self.state = RuntimeState.COOLDOWN
            self.previous_gesture = self.current_gesture
            self.current_gesture = detected_gesture
            return self.state

        if self.state == RuntimeState.COOLDOWN:
            # Cooldown just ended.
            self.state = RuntimeState.WAITING

        # Gesture changed (including changing to/from UNKNOWN) -> restart timer.
        if detected_gesture != self.current_gesture:
            self.previous_gesture = self.current_gesture
            self.current_gesture = detected_gesture
            self._gesture_start_time = now if detected_gesture != GESTURE_UNKNOWN else None

            self.state = (
                RuntimeState.GESTURE_DETECTED
                if detected_gesture != GESTURE_UNKNOWN
                else RuntimeState.WAITING
            )
            return self.state

        # Same gesture as last frame — check whether it's been held long enough.
        if detected_gesture == GESTURE_UNKNOWN:
            self.state = RuntimeState.UNKNOWN
            return self.state

        if self._gesture_start_time is None:
            self._gesture_start_time = now

        held_for = now - self._gesture_start_time
        if held_for >= self.stability_seconds:
            self.state = RuntimeState.GESTURE_STABLE
        else:
            self.state = RuntimeState.GESTURE_DETECTED

        return self.state

    def should_execute(self) -> bool:
        """
        True exactly once per stable gesture hold: when the gesture has just
        become stable and hasn't already been executed for this hold.
        """
        if self.state != RuntimeState.GESTURE_STABLE:
            return False
        if self.last_executed_gesture == self.current_gesture:
            return False
        return True

    def mark_executed(self) -> None:
        self.last_executed_gesture = self.current_gesture
        self.state = RuntimeState.ACTION_EXECUTED
        self._cooldown_until = time.monotonic() + self.cooldown_seconds
        log.info(
            "Executed action for gesture=%s; cooldown for %.1fs",
            self.current_gesture, self.cooldown_seconds,
        )
        self.state = RuntimeState.COOLDOWN

    def reset_execution_lock(self) -> None:
        """Called once a gesture disappears/changes, so the same gesture can fire again later."""
        self.last_executed_gesture = None
