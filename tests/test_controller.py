"""
Unit tests for core/controller.py.

These tests focus on the gesture-processing boundary so we can verify the
stateful hold-hotkey flow without opening a camera or touching the GUI.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.controller import Controller
from core.state import GestureState
from utils.constants import (
    ACTION_BATCH,
    ACTION_HOLD_HOTKEY,
    ACTION_HOTKEY,
    GESTURE_UNKNOWN,
)


class FakeMappingManager:
    def __init__(self, mappings):
        self._mappings = mappings

    def get_action(self, gesture):
        return self._mappings.get(gesture)


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def start_hold_hotkey(self, action_entry):
        self.calls.append(("start", action_entry))

    def repeat_hold_hotkey(self):
        self.calls.append(("repeat", None))
        return True

    def stop_active_sessions(self):
        self.calls.append(("stop", None))

    def execute(self, action_entry):
        self.calls.append(("execute", action_entry))


def test_controller_starts_repeats_and_stops_hold_hotkey():
    fake_executor = FakeExecutor()
    controller = Controller(
        camera=object(),
        mapping_manager=FakeMappingManager(
            {
                "CLOSE_TAB": {
                    "type": ACTION_HOLD_HOTKEY,
                    "modifier": "alt",
                    "key": "tab",
                    "enabled": True,
                },
                "NEXT_TAB": {
                    "type": ACTION_HOTKEY,
                    "keys": ["ctrl", "tab"],
                    "enabled": True,
                },
                "V_SHAPE": {
                    "type": ACTION_BATCH,
                    "path": r"C:\Automation\chrome.bat",
                    "enabled": True,
                },
            }
        ),
        executor=fake_executor,
    )
    controller.gesture_state = GestureState(stability_seconds=0.0, cooldown_seconds=0.0)

    controller.process_gesture("CLOSE_TAB")
    controller.process_gesture("CLOSE_TAB")
    controller.process_gesture(GESTURE_UNKNOWN)

    assert fake_executor.calls[0][0] == "start"
    assert fake_executor.calls[1][0] == "repeat"
    assert fake_executor.calls[-1][0] == "stop"

    controller.process_gesture("NEXT_TAB")
    controller.process_gesture("NEXT_TAB")

    assert ("execute", controller.mapping_manager.get_action("NEXT_TAB")) in fake_executor.calls
