"""
Unit tests for execution/executor.py.

Uses monkeypatch to avoid actually launching processes during tests.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from execution.executor import ExecutionError, Executor


def test_unsupported_action_type_raises():
    executor = Executor()
    with pytest.raises(ExecutionError):
        executor.execute({"type": "powershell", "path": "C:\\x.ps1"})


def test_missing_batch_file_raises(tmp_path):
    executor = Executor()
    missing = tmp_path / "does_not_exist.bat"
    with pytest.raises(ExecutionError):
        executor.execute({"type": "batch", "path": str(missing)})


def test_non_bat_extension_refused(tmp_path):
    fake_exe = tmp_path / "not_a_batch.exe"
    fake_exe.write_text("echo hi")
    executor = Executor()
    with pytest.raises(ExecutionError):
        executor.execute({"type": "batch", "path": str(fake_exe)})


def test_valid_batch_file_launches_subprocess(tmp_path, monkeypatch):
    bat_file = tmp_path / "action.bat"
    bat_file.write_text("@echo off\necho hello\n")

    called = {}

    def fake_popen(cmd, cwd=None, shell=False):
        called["cmd"] = cmd
        called["cwd"] = cwd

        class FakeProcess:
            pass

        return FakeProcess()

    monkeypatch.setattr("execution.executor.subprocess.Popen", fake_popen)

    executor = Executor()
    executor.execute({"type": "batch", "path": str(bat_file)})

    assert called["cmd"][-1] == str(bat_file)
    assert called["cwd"] == str(tmp_path)


def test_hotkey_action_calls_pyautogui(monkeypatch):
    called = {}

    class FakePyAutoGUI:
        def hotkey(self, *keys):
            called["keys"] = keys

    monkeypatch.setattr("execution.executor.pyautogui", FakePyAutoGUI())

    executor = Executor()
    executor.execute({"type": "hotkey", "keys": ["ctrl", "tab"]})

    assert called["keys"] == ("ctrl", "tab")


def test_hold_hotkey_session_starts_repeats_and_stops(monkeypatch):
    events = []

    class FakePyAutoGUI:
        def keyDown(self, key):
            events.append(("down", key))

        def press(self, key):
            events.append(("press", key))

        def keyUp(self, key):
            events.append(("up", key))

        def hotkey(self, *keys):
            events.append(("hotkey", keys))

    times = iter([100.0, 100.1, 100.5, 101.0])

    monkeypatch.setattr("execution.executor.pyautogui", FakePyAutoGUI())
    monkeypatch.setattr("execution.executor.time.monotonic", lambda: next(times))

    executor = Executor()
    executor.start_hold_hotkey({"type": "hold_hotkey", "modifier": "alt", "key": "tab"})

    assert events[:2] == [("down", "alt"), ("press", "tab")]

    assert executor.repeat_hold_hotkey() is False
    assert executor.repeat_hold_hotkey() is True

    executor.stop_active_sessions()
    assert events[-1] == ("up", "alt")
