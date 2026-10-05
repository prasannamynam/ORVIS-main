"""
Shared constants for ORVIX.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Gestures
# ---------------------------------------------------------------------------

GESTURE_V_SHAPE = "V_SHAPE"
GESTURE_THUMBS_UP = "THUMBS_UP"
GESTURE_FIST = "FIST"
GESTURE_OPEN_PALM = "OPEN_PALM"
GESTURE_PALM_PALM = "PALM_PALM"
GESTURE_UNKNOWN = "UNKNOWN"
GESTURE_ONE_FINGER = "ONE_FINGER"
GESTURE_THREE_FINGER = "THREE_FINGER"
GESTURE_ROCK_SIGN = "ROCK_SIGN"
GESTURE_CALL_SIGN = "CALL_SIGN"
GESTURE_OK_SIGN = "OK_SIGN"

# ---------------------------------------------------------------------------
# Semantic two-hand commands
# ---------------------------------------------------------------------------

COMMAND_NEXT_TAB = "NEXT_TAB"
COMMAND_PREVIOUS_TAB = "PREVIOUS_TAB"
COMMAND_NEW_TAB = "NEW_TAB"
COMMAND_CLOSE_TAB = "CLOSE_TAB"

# ---------------------------------------------------------------------------
# Action types
# ---------------------------------------------------------------------------

ACTION_BATCH = "batch"
ACTION_HOTKEY = "hotkey"
ACTION_HOLD_HOTKEY = "hold_hotkey"

# These are the gestures that can be mapped to actions.
#
# OPEN_PALM is intentionally NOT included as an executable gesture.
# It is used as the activation hand.
GESTURES = [
    GESTURE_V_SHAPE,
    GESTURE_THUMBS_UP,
    GESTURE_FIST,

    GESTURE_ONE_FINGER,
    GESTURE_THREE_FINGER,
    GESTURE_ROCK_SIGN,
    GESTURE_CALL_SIGN,
    GESTURE_OK_SIGN,

    GESTURE_PALM_PALM,
]

# These are the names the GUI exposes for creating mappings.
# OPEN_PALM stays out of the list because it is the modifier hand, not an
# executable action.
MAPPABLE_GESTURES = GESTURES + [
    COMMAND_NEXT_TAB,
    COMMAND_PREVIOUS_TAB,
    COMMAND_NEW_TAB,
    COMMAND_CLOSE_TAB,
]

ACTION_TYPES = [
    ACTION_BATCH,
    ACTION_HOTKEY,
    ACTION_HOLD_HOTKEY,
]

# Repeat interval for hold-hotkey sessions such as Alt+Tab.
ALT_TAB_REPEAT_INTERVAL = 0.4
# ---------------------------------------------------------------------------
# Hand landmark indices (MediaPipe HandLandmarker, 21 points)
# ---------------------------------------------------------------------------

WRIST = 0

THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4

INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8

MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12

RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16

LITTLE_MCP, LITTLE_PIP, LITTLE_DIP, LITTLE_TIP = 17, 18, 19, 20

# ---------------------------------------------------------------------------
# Timing / stability thresholds
# ---------------------------------------------------------------------------

# Gesture must remain stable for this duration before execution.
GESTURE_STABILITY_SECONDS = 0.0

# Wait this long after execution before allowing another execution.
COOLDOWN_SECONDS = 1.0

# ---------------------------------------------------------------------------
# MediaPipe configuration
# ---------------------------------------------------------------------------

MIN_HAND_DETECTION_CONFIDENCE = 0.6
MIN_HAND_PRESENCE_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.6

# IMPORTANT:
# ORVIX now supports two-hand gestures.
MAX_NUM_HANDS = 2

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    PROJECT_ROOT
    / "hand"
    / "models"
    / "hand_landmarker.task"
)

CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "mappings.json"
)

LOG_PATH = PROJECT_ROOT / "orvix.log"
