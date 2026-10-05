"""
Unit tests for gesture/recognizer.py.

Builds synthetic 21-point landmark sets by hand (normalized 0..1 image
coordinates, y grows downward) instead of using a real camera, so these
tests run anywhere without a webcam or model file.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gesture.recognizer import GestureRecognizer
from utils.constants import (
    GESTURE_FIST,
    GESTURE_OPEN_PALM,
    GESTURE_ONE_FINGER,
    GESTURE_PALM_PALM,
    GESTURE_CALL_SIGN,
    GESTURE_OK_SIGN,
    GESTURE_THREE_FINGER,
    GESTURE_THUMBS_UP,
    GESTURE_UNKNOWN,
    GESTURE_V_SHAPE,
    COMMAND_CLOSE_TAB,
    COMMAND_NEXT_TAB,
    COMMAND_NEW_TAB,
    COMMAND_PREVIOUS_TAB,
)


def _blank_hand():
    """21 landmarks, all folded into the palm (baseline for a fist)."""
    palm_y = 0.5
    lm = [[0.5, 0.55, 0.0] for _ in range(21)]  # wrist + everything else near palm
    # thumb folded: tip close to wrist, not extended, not above IP
    lm[1] = [0.45, 0.55, 0.0]
    lm[2] = [0.44, 0.55, 0.0]
    lm[3] = [0.43, 0.55, 0.0]
    lm[4] = [0.43, 0.56, 0.0]  # tip
    # index folded: tip below (greater y) than pip
    lm[5] = [0.5, 0.5, 0.0]
    lm[6] = [0.5, 0.48, 0.0]
    lm[7] = [0.5, 0.5, 0.0]
    lm[8] = [0.5, 0.52, 0.0]  # tip below pip
    # middle folded
    lm[9] = [0.52, 0.5, 0.0]
    lm[10] = [0.52, 0.47, 0.0]
    lm[11] = [0.52, 0.5, 0.0]
    lm[12] = [0.52, 0.52, 0.0]
    # ring folded
    lm[13] = [0.54, 0.5, 0.0]
    lm[14] = [0.54, 0.47, 0.0]
    lm[15] = [0.54, 0.5, 0.0]
    lm[16] = [0.54, 0.52, 0.0]
    # little folded
    lm[17] = [0.56, 0.5, 0.0]
    lm[18] = [0.56, 0.48, 0.0]
    lm[19] = [0.56, 0.5, 0.0]
    lm[20] = [0.56, 0.52, 0.0]
    lm[0] = [0.5, 0.6, 0.0]  # wrist
    return lm


def _extend_finger(lm, mcp, pip, tip):
    """Push a finger's tip well above its pip (UP)."""
    lm[tip] = [lm[pip][0], lm[pip][1] - 0.15, 0.0]
    return lm


def _open_palm_hand():
    lm = _blank_hand()
    lm = _extend_finger(lm, 5, 6, 8)    # index up
    lm = _extend_finger(lm, 9, 10, 12)  # middle up
    lm = _extend_finger(lm, 13, 14, 16) # ring up
    lm = _extend_finger(lm, 17, 18, 20) # little up
    return lm


def _one_finger_hand():
    lm = _blank_hand()
    lm = _extend_finger(lm, 5, 6, 8)
    return lm


def _v_shape_hand():
    lm = _blank_hand()
    lm = _extend_finger(lm, 5, 6, 8)
    lm = _extend_finger(lm, 9, 10, 12)
    return lm


def _three_finger_hand():
    lm = _blank_hand()
    lm = _extend_finger(lm, 5, 6, 8)
    lm = _extend_finger(lm, 9, 10, 12)
    lm = _extend_finger(lm, 13, 14, 16)
    return lm


def _ok_sign_hand():
    lm = _blank_hand()
    lm = _extend_finger(lm, 9, 10, 12)
    lm = _extend_finger(lm, 13, 14, 16)
    lm = _extend_finger(lm, 17, 18, 20)
    lm[4] = [0.50, 0.43, 0.0]
    lm[8] = [0.52, 0.44, 0.0]
    return lm


def _call_sign_hand():
    lm = _blank_hand()
    lm[0] = [0.5, 0.7, 0.0]
    lm[2] = [0.5, 0.6, 0.0]
    lm[3] = [0.5, 0.5, 0.0]
    lm[4] = [0.5, 0.35, 0.0]
    lm = _extend_finger(lm, 17, 18, 20)
    return lm


def test_fist_is_recognized():
    lm = _blank_hand()
    gesture = GestureRecognizer().recognize(lm)
    assert gesture == GESTURE_FIST


def test_v_shape_is_recognized():
    lm = _blank_hand()
    lm = _extend_finger(lm, 5, 6, 8)    # index up
    lm = _extend_finger(lm, 9, 10, 12)  # middle up
    gesture = GestureRecognizer().recognize(lm)
    assert gesture == GESTURE_V_SHAPE


def test_open_palm_is_recognized():
    lm = _blank_hand()
    lm = _extend_finger(lm, 5, 6, 8)
    lm = _extend_finger(lm, 9, 10, 12)
    lm = _extend_finger(lm, 13, 14, 16)
    lm = _extend_finger(lm, 17, 18, 20)
    gesture = GestureRecognizer().recognize(lm)
    assert gesture == GESTURE_OPEN_PALM


def test_thumbs_up_is_recognized():
    lm = _blank_hand()
    # Extend thumb: tip far from wrist and above the IP joint.
    lm[0] = [0.5, 0.7, 0.0]     # wrist
    lm[2] = [0.5, 0.6, 0.0]     # thumb mcp
    lm[3] = [0.5, 0.5, 0.0]     # thumb ip
    lm[4] = [0.5, 0.35, 0.0]    # thumb tip, well above ip and far from wrist
    gesture = GestureRecognizer().recognize(lm)
    assert gesture == GESTURE_THUMBS_UP


def test_no_landmarks_returns_unknown():
    gesture = GestureRecognizer().recognize(None)
    assert gesture == GESTURE_UNKNOWN


def test_wrong_landmark_count_returns_unknown():
    gesture = GestureRecognizer().recognize([[0, 0, 0]] * 5)
    assert gesture == GESTURE_UNKNOWN


def test_open_palm_and_one_finger_resolves_next_tab():
    recognizer = GestureRecognizer()
    assert recognizer.recognize_two_hands([_open_palm_hand(), _one_finger_hand()]) == COMMAND_NEXT_TAB
    assert recognizer.recognize_two_hands([_one_finger_hand(), _open_palm_hand()]) == COMMAND_NEXT_TAB


def test_open_palm_and_v_shape_still_resolves_v_shape():
    recognizer = GestureRecognizer()
    assert recognizer.recognize_two_hands([_open_palm_hand(), _v_shape_hand()]) == GESTURE_V_SHAPE
    assert recognizer.recognize_two_hands([_v_shape_hand(), _open_palm_hand()]) == GESTURE_V_SHAPE


def test_open_palm_and_three_finger_resolves_previous_tab():
    recognizer = GestureRecognizer()
    assert recognizer.recognize_two_hands([_open_palm_hand(), _three_finger_hand()]) == COMMAND_PREVIOUS_TAB
    assert recognizer.recognize_two_hands([_three_finger_hand(), _open_palm_hand()]) == COMMAND_PREVIOUS_TAB


def test_open_palm_and_ok_sign_resolves_new_tab():
    recognizer = GestureRecognizer()
    assert recognizer.recognize_two_hands([_open_palm_hand(), _ok_sign_hand()]) == COMMAND_NEW_TAB
    assert recognizer.recognize_two_hands([_ok_sign_hand(), _open_palm_hand()]) == COMMAND_NEW_TAB


def test_open_palm_and_call_sign_resolves_close_tab():
    recognizer = GestureRecognizer()
    assert recognizer.recognize_two_hands([_open_palm_hand(), _call_sign_hand()]) == COMMAND_CLOSE_TAB
    assert recognizer.recognize_two_hands([_call_sign_hand(), _open_palm_hand()]) == COMMAND_CLOSE_TAB


def test_open_palm_and_fist_is_no_longer_close_tab():
    recognizer = GestureRecognizer()
    assert recognizer.recognize_two_hands([_open_palm_hand(), _blank_hand()]) == GESTURE_UNKNOWN


def test_open_palm_and_open_palm_resolves_palm_palm():
    recognizer = GestureRecognizer()
    assert recognizer.recognize_two_hands([_open_palm_hand(), _open_palm_hand()]) == GESTURE_PALM_PALM


def test_invalid_two_hand_combinations_return_unknown():
    recognizer = GestureRecognizer()
    assert recognizer.recognize_two_hands([_blank_hand(), _one_finger_hand()]) == GESTURE_UNKNOWN
    assert recognizer.recognize_two_hands([_open_palm_hand(), _blank_hand(), _blank_hand()]) == GESTURE_UNKNOWN
