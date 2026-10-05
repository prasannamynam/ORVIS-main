"""
gesture/recognizer.py

Responsible for:

- Receiving hand landmarks
- Determining finger states
- Recognizing individual hand gestures
- Resolving valid two-hand ORVIX commands

ORVIX gesture architecture:

    Activation hand:
        OPEN_PALM

    Command hand:
        V_SHAPE
        THUMBS_UP
        FIST
        ONE_FINGER
        THREE_FINGER
        ROCK_SIGN
        CALL_SIGN
        OK_SIGN

    Special two-hand command:
        OPEN_PALM + OPEN_PALM
            -> PALM_PALM

    Semantic two-hand commands:
        OPEN_PALM + ONE_FINGER
            -> NEXT_TAB
        OPEN_PALM + THREE_FINGER
            -> PREVIOUS_TAB
        OPEN_PALM + OK_SIGN
            -> NEW_TAB
        OPEN_PALM + CALL_SIGN
            -> CLOSE_TAB

This module knows NOTHING about batch files or actions.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from utils.constants import (
    # Existing gestures
    GESTURE_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_THUMBS_UP,
    GESTURE_UNKNOWN,
    GESTURE_V_SHAPE,

    # New gestures
    GESTURE_ONE_FINGER,
    GESTURE_THREE_FINGER,
    GESTURE_ROCK_SIGN,
    GESTURE_CALL_SIGN,
    GESTURE_OK_SIGN,
    GESTURE_PALM_PALM,

    # Semantic commands
    COMMAND_CLOSE_TAB,
    COMMAND_NEXT_TAB,
    COMMAND_NEW_TAB,
    COMMAND_PREVIOUS_TAB,

    # Landmark indices
    INDEX_PIP,
    INDEX_TIP,

    LITTLE_PIP,
    LITTLE_TIP,

    MIDDLE_PIP,
    MIDDLE_TIP,

    RING_PIP,
    RING_TIP,

    THUMB_IP,
    THUMB_MCP,
    THUMB_TIP,

    WRIST,
)

from utils.logger import get_logger


log = get_logger("gesture.recognizer")


# ============================================================================
# Types
# ============================================================================

class FingerState(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


Landmarks = List[List[float]]


# ============================================================================
# Gesture Recognizer
# ============================================================================

class GestureRecognizer:
    """
    Recognizes individual hand gestures and resolves
    two-hand ORVIX commands.
    """

    # ========================================================================
    # Individual Hand Recognition
    # ========================================================================

    def recognize(
        self,
        landmarks: Optional[Landmarks],
    ) -> str:

        # --------------------------------------------------------------
        # Validate landmarks
        # --------------------------------------------------------------

        if (
            landmarks is None
            or len(landmarks) != 21
        ):
            return GESTURE_UNKNOWN

        # --------------------------------------------------------------
        # Determine finger states
        # --------------------------------------------------------------

        index = self._finger_up(
            landmarks,
            INDEX_TIP,
            INDEX_PIP,
        )

        middle = self._finger_up(
            landmarks,
            MIDDLE_TIP,
            MIDDLE_PIP,
        )

        ring = self._finger_up(
            landmarks,
            RING_TIP,
            RING_PIP,
        )

        little = self._finger_up(
            landmarks,
            LITTLE_TIP,
            LITTLE_PIP,
        )

        thumb = self._thumb_up(
            landmarks
        )

        # --------------------------------------------------------------
        # Detect OK sign separately.
        #
        # OK sign depends on the distance between the thumb and
        # index fingertips, so it cannot be determined only from
        # UP / DOWN states.
        # --------------------------------------------------------------

        ok_sign = self._is_ok_sign(
            landmarks,
            index,
            middle,
            ring,
            little,
        )

        # --------------------------------------------------------------
        # Classify gesture
        # --------------------------------------------------------------

        gesture = self._classify(
            thumb,
            index,
            middle,
            ring,
            little,
            ok_sign,
        )

        log.debug(
            "Individual hand: "
            "thumb=%s index=%s middle=%s "
            "ring=%s little=%s ok=%s -> %s",
            thumb.value,
            index.value,
            middle.value,
            ring.value,
            little.value,
            ok_sign,
            gesture,
        )

        return gesture

    # ========================================================================
    # Two-Hand Recognition
    # ========================================================================

    def recognize_two_hands(
        self,
        hands: List[Landmarks],
    ) -> str:
        """
        Resolves a valid ORVIX command from exactly two hands.

        Valid combinations:

            OPEN_PALM + ONE_FINGER
                -> NEXT_TAB

            OPEN_PALM + THREE_FINGER
                -> PREVIOUS_TAB

            OPEN_PALM + OK_SIGN
                -> NEW_TAB

        OPEN_PALM + CALL_SIGN
            -> CLOSE_TAB

            OPEN_PALM + OPEN_PALM
                -> PALM_PALM

        Anything else returns UNKNOWN.
        """

        # --------------------------------------------------------------
        # Exactly two hands are required
        # --------------------------------------------------------------

        if len(hands) != 2:

            log.debug(
                "Two-hand recognition requires exactly 2 hands. "
                "Found %d.",
                len(hands),
            )

            return GESTURE_UNKNOWN

        # --------------------------------------------------------------
        # Recognize each hand individually
        # --------------------------------------------------------------

        gesture_a = self.recognize(
            hands[0]
        )

        gesture_b = self.recognize(
            hands[1]
        )

        log.debug(
            "Two-hand combination: %s + %s",
            gesture_a,
            gesture_b,
        )

        # ==============================================================
        # PALM + PALM
        # ==============================================================

        if (
            gesture_a == GESTURE_OPEN_PALM
            and
            gesture_b == GESTURE_OPEN_PALM
        ):

            log.info(
                "Recognized PALM_PALM"
            )

            return GESTURE_PALM_PALM

        command = self._resolve_command_pair(
            gesture_a,
            gesture_b,
        )

        if command != GESTURE_UNKNOWN:
            return command

        # ==============================================================
        # No valid activation/command pair
        # ==============================================================

        log.debug(
            "No valid OPEN_PALM + command pairing found."
        )

        return GESTURE_UNKNOWN

    # ========================================================================
    # Command Resolver
    # ========================================================================

    @staticmethod
    def _resolve_command_pair(
        gesture_a: str,
        gesture_b: str,
    ) -> str:
        """
        Resolves the semantic command for a two-hand combination.

        The modifier hand must be OPEN_PALM and the command hand must be one
        of the supported command gestures.
        """

        command_map = {
            GESTURE_V_SHAPE: GESTURE_V_SHAPE,
            GESTURE_THUMBS_UP: GESTURE_THUMBS_UP,
            GESTURE_ONE_FINGER: COMMAND_NEXT_TAB,
            GESTURE_THREE_FINGER: COMMAND_PREVIOUS_TAB,
            GESTURE_OK_SIGN: COMMAND_NEW_TAB,
            GESTURE_CALL_SIGN: COMMAND_CLOSE_TAB,
            GESTURE_ROCK_SIGN: GESTURE_ROCK_SIGN,
        }

        gestures = (gesture_a, gesture_b)
        open_palm_count = gestures.count(GESTURE_OPEN_PALM)

        if open_palm_count != 1:
            return GESTURE_UNKNOWN

        command_gesture = (
            gesture_b
            if gesture_a == GESTURE_OPEN_PALM
            else gesture_a
        )

        command = command_map.get(command_gesture, GESTURE_UNKNOWN)

        if command != GESTURE_UNKNOWN:
            log.info(
                "Recognized two-hand command: %s + %s -> %s",
                GESTURE_OPEN_PALM,
                command_gesture,
                command,
            )

        return command

    # ========================================================================
    # Finger State Helpers
    # ========================================================================

    @staticmethod
    def _finger_up(
        landmarks: Landmarks,
        tip_idx: int,
        pip_idx: int,
    ) -> FingerState:
        """
        Determines whether a non-thumb finger is extended.

        MediaPipe uses normalized image coordinates:

            y = 0 -> top of image
            y = 1 -> bottom of image

        Therefore:

            smaller tip.y than pip.y -> finger is UP
        """

        tip_y = landmarks[tip_idx][1]

        pip_y = landmarks[pip_idx][1]

        margin = 0.02

        if tip_y < pip_y - margin:
            return FingerState.UP

        return FingerState.DOWN

    # ========================================================================
    # Thumb Detection
    # ========================================================================

    @staticmethod
    def _thumb_up(
        landmarks: Landmarks,
    ) -> FingerState:
        """
        Determines whether the thumb is extended upward.

        This is mainly useful for THUMBS_UP and CALL_SIGN.
        """

        wrist = landmarks[WRIST]

        tip = landmarks[THUMB_TIP]

        mcp = landmarks[THUMB_MCP]

        ip = landmarks[THUMB_IP]

        # --------------------------------------------------------------
        # Thumb tip must be above IP joint
        # --------------------------------------------------------------

        tip_above_ip = (
            tip[1]
            <
            ip[1] - 0.02
        )

        # --------------------------------------------------------------
        # Compare distance from wrist
        # --------------------------------------------------------------

        dist_tip_wrist = (
            (
                (tip[0] - wrist[0]) ** 2
                +
                (tip[1] - wrist[1]) ** 2
            )
            ** 0.5
        )

        dist_mcp_wrist = (
            (
                (mcp[0] - wrist[0]) ** 2
                +
                (mcp[1] - wrist[1]) ** 2
            )
            ** 0.5
        )

        extended = (
            dist_tip_wrist
            >
            dist_mcp_wrist * 1.15
        )

        if tip_above_ip and extended:
            return FingerState.UP

        return FingerState.DOWN

    # ========================================================================
    # OK Sign Detection
    # ========================================================================

    @staticmethod
    def _is_ok_sign(
        landmarks: Landmarks,
        index: FingerState,
        middle: FingerState,
        ring: FingerState,
        little: FingerState,
    ) -> bool:
        """
        Detects an OK sign.

        Basic geometry:

            thumb tip
                  \
                   O <- index tip
                  /
            thumb + index form a small circle

        The middle, ring and little fingers should remain extended.

        We use normalized landmark coordinates, so the threshold is
        scale-independent enough for normal webcam usage.
        """

        # --------------------------------------------------------------
        # Other three fingers should be extended.
        #
        # This avoids confusing OK_SIGN with:
        #
        #     FIST
        #     THUMBS_UP
        # --------------------------------------------------------------

        if not (
            middle == FingerState.UP
            and
            ring == FingerState.UP
            and
            little == FingerState.UP
        ):
            return False

        # --------------------------------------------------------------
        # Thumb tip
        # --------------------------------------------------------------

        thumb_tip = landmarks[THUMB_TIP]

        # --------------------------------------------------------------
        # Index tip
        # --------------------------------------------------------------

        index_tip = landmarks[INDEX_TIP]

        # --------------------------------------------------------------
        # Euclidean distance between thumb tip and index tip
        # --------------------------------------------------------------

        distance = (
            (
                (thumb_tip[0] - index_tip[0]) ** 2
                +
                (thumb_tip[1] - index_tip[1]) ** 2
            )
            ** 0.5
        )

        # --------------------------------------------------------------
        # Threshold
        #
        # Since coordinates are normalized 0..1:
        #
        # ~0.08 = fingers are very close
        # --------------------------------------------------------------

        OK_DISTANCE_THRESHOLD = 0.08

        return distance < OK_DISTANCE_THRESHOLD

    # ========================================================================
    # Classification
    # ========================================================================

    @staticmethod
    def _classify(
        thumb: FingerState,
        index: FingerState,
        middle: FingerState,
        ring: FingerState,
        little: FingerState,
        ok_sign: bool = False,
    ) -> str:

        U = FingerState.UP
        D = FingerState.DOWN

        # ==============================================================
        # OK SIGN
        # ==============================================================
        #
        # 👌
        #
        # Thumb + index form a circle.
        # Middle + ring + little are extended.
        #
        # This is checked first because the index finger may not
        # satisfy the normal UP/DOWN classification.
        # ==============================================================

        if ok_sign:
            return GESTURE_OK_SIGN

        # ==============================================================
        # V SHAPE
        # ==============================================================

        if (
            index == U
            and
            middle == U
            and
            ring == D
            and
            little == D
        ):
            return GESTURE_V_SHAPE

        # ==============================================================
        # ONE FINGER
        #
        # ☝️
        #
        # Index = UP
        # Middle = DOWN
        # Ring = DOWN
        # Little = DOWN
        #
        # Thumb can be either state because different hand
        # orientations can affect thumb detection.
        # ==============================================================

        if (
            index == U
            and
            middle == D
            and
            ring == D
            and
            little == D
        ):
            return GESTURE_ONE_FINGER

        # ==============================================================
        # THREE FINGER
        #
        # Index  = UP
        # Middle = UP
        # Ring   = UP
        # Little = DOWN
        # ==============================================================

        if (
            index == U
            and
            middle == U
            and
            ring == U
            and
            little == D
        ):
            return GESTURE_THREE_FINGER

        # ==============================================================
        # ROCK SIGN
        #
        # 🤘
        #
        # Index  = UP
        # Middle = DOWN
        # Ring   = DOWN
        # Little = UP
        # ==============================================================

        if (
            index == U
            and
            middle == D
            and
            ring == D
            and
            little == U
        ):
            return GESTURE_ROCK_SIGN

        # ==============================================================
        # CALL SIGN
        #
        # 🤙
        #
        # Thumb  = UP
        # Index  = DOWN
        # Middle = DOWN
        # Ring   = DOWN
        # Little = UP
        # ==============================================================

        if (
            thumb == U
            and
            index == D
            and
            middle == D
            and
            ring == D
            and
            little == U
        ):
            return GESTURE_CALL_SIGN

        # ==============================================================
        # THUMBS UP
        #
        # 👍
        #
        # Thumb = UP
        # Other fingers = DOWN
        # ==============================================================

        if (
            index == D
            and
            middle == D
            and
            ring == D
            and
            little == D
            and
            thumb == U
        ):
            return GESTURE_THUMBS_UP

        # ==============================================================
        # FIST
        #
        # ✊
        #
        # All fingers = DOWN
        # ==============================================================

        if (
            index == D
            and
            middle == D
            and
            ring == D
            and
            little == D
            and
            thumb == D
        ):
            return GESTURE_FIST

        # ==============================================================
        # OPEN PALM
        #
        # ✋
        #
        # All four main fingers extended.
        #
        # We intentionally don't require thumb == UP here because
        # thumb orientation can vary depending on whether the hand
        # is the left or right hand and camera position.
        # ==============================================================

        if (
            index == U
            and
            middle == U
            and
            ring == U
            and
            little == U
        ):
            return GESTURE_OPEN_PALM

        # ==============================================================
        # Unknown
        # ==============================================================

        return GESTURE_UNKNOWN
