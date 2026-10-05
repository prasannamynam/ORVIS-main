"""
execution/executor.py

Responsible for:
- Receiving an approved action entry (from mapping/manager.py)
- Executing it
- Handling execution errors

V1 only implements the "batch" action type, but the dispatch table makes it
trivial to add "exe", "url", "powershell", "python", "command", "hotkey"
later without touching the controller or GUI.

Security note (see spec section 21): this executor NEVER runs arbitrary
strings. It only runs the exact path the user configured through the GUI,
and only for action types explicitly enabled below.
"""

from __future__ import annotations

import atexit
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict

from utils.constants import (
    ACTION_BATCH,
    ACTION_HOLD_HOTKEY,
    ACTION_HOTKEY,
    ALT_TAB_REPEAT_INTERVAL,
)
from utils.logger import get_logger

log = get_logger("execution.executor")

try:
    import pyautogui
except Exception:  # pragma: no cover - optional runtime dependency
    pyautogui = None


class ExecutionError(RuntimeError):
    pass


@dataclass
class HoldHotkeySession:
    modifier: str
    key: str
    repeat_interval: float = ALT_TAB_REPEAT_INTERVAL
    last_press_at: float = 0.0


class Executor:
    def __init__(self):
        self._dispatch: Dict[str, Callable[[dict], None]] = {
            ACTION_BATCH: self._run_batch,
            ACTION_HOTKEY: self._run_hotkey,
            ACTION_HOLD_HOTKEY: self._start_hold_hotkey,
        }
        self._active_hold_session: HoldHotkeySession | None = None
        atexit.register(self.stop_active_sessions)

    def execute(self, action_entry: dict) -> None:
        action_type = action_entry.get("type")
        handler = self._dispatch.get(action_type)

        if handler is None:
            raise ExecutionError(f"Unsupported action type: '{action_type}'")

        handler(action_entry)

    def start_hold_hotkey(self, action_entry: dict) -> None:
        self._start_hold_hotkey(action_entry)

    def repeat_hold_hotkey(self) -> bool:
        session = self._active_hold_session
        if session is None:
            return False

        now = time.monotonic()
        if now - session.last_press_at < session.repeat_interval:
            return False

        log.info("Repeating hold hotkey: %s + %s", session.modifier, session.key)
        try:
            pyautogui.press(session.key)
        except Exception as e:
            raise ExecutionError(f"Failed to repeat hold hotkey {session.modifier} + {session.key}: {e}") from e

        session.last_press_at = now
        return True

    def stop_active_sessions(self) -> None:
        session = self._active_hold_session
        if session is None:
            return

        self._active_hold_session = None
        log.info("Releasing hold hotkey: %s", session.modifier)
        try:
            if pyautogui is not None:
                pyautogui.keyUp(session.modifier)
        except Exception as e:
            log.error("Failed to release hold hotkey %s: %s", session.modifier, e)

    def release_all_keys(self) -> None:
        self.stop_active_sessions()

    def close(self) -> None:
        self.stop_active_sessions()

    # ------------------------------------------------------------------
    # V1 handler
    # ------------------------------------------------------------------

    def _run_batch(self, action_entry: dict) -> None:
        path = Path(action_entry.get("path", ""))

        if not path.exists():
            raise ExecutionError(f"Batch file not found: {path}")
        if path.suffix.lower() != ".bat":
            raise ExecutionError(f"Refusing to execute non-.bat file: {path}")

        log.info("Executing batch file: %s", path)
        try:
            # start /wait not used deliberately — we don't want to block the
            # gesture loop waiting for the launched program to close.
            subprocess.Popen(
                ["cmd.exe", "/c", str(path)],
                cwd=str(path.parent),
                shell=False,
            )
        except OSError as e:
            raise ExecutionError(f"Failed to execute {path}: {e}") from e

    def _run_hotkey(self, action_entry: dict) -> None:
        if pyautogui is None:
            raise ExecutionError(
                "pyautogui is required for hotkey actions but is not installed"
            )

        keys = action_entry.get("keys")
        if not isinstance(keys, (list, tuple)) or not keys:
            raise ExecutionError("Hotkey action requires a non-empty 'keys' list")

        normalized_keys = [str(key).strip() for key in keys if str(key).strip()]
        if not normalized_keys:
            raise ExecutionError("Hotkey action requires at least one valid key")

        log.info("Executing hotkey: %s", " + ".join(normalized_keys))
        try:
            pyautogui.hotkey(*normalized_keys)
        except Exception as e:
            raise ExecutionError(f"Failed to execute hotkey {normalized_keys}: {e}") from e

    # ------------------------------------------------------------------
    # Hold hotkey session
    # ------------------------------------------------------------------

    def _start_hold_hotkey(self, action_entry: dict) -> None:
        if pyautogui is None:
            raise ExecutionError(
                "pyautogui is required for hold_hotkey actions but is not installed"
            )

        modifier = str(action_entry.get("modifier", "")).strip().lower()
        key = str(action_entry.get("key", "")).strip().lower()
        if not modifier or not key:
            raise ExecutionError("Hold hotkey action requires 'modifier' and 'key'")

        repeat_interval = action_entry.get("repeat_interval", ALT_TAB_REPEAT_INTERVAL)
        try:
            repeat_interval = float(repeat_interval)
        except (TypeError, ValueError) as e:
            raise ExecutionError(f"Invalid repeat_interval for hold hotkey: {repeat_interval}") from e

        current = self._active_hold_session
        if current is not None:
            same_session = (
                current.modifier == modifier
                and current.key == key
                and current.repeat_interval == repeat_interval
            )
            if same_session:
                return
            self.stop_active_sessions()

        log.info("Starting hold hotkey: %s + %s", modifier, key)
        try:
            pyautogui.keyDown(modifier)
            pyautogui.press(key)
        except Exception as e:
            try:
                pyautogui.keyUp(modifier)
            except Exception as release_error:
                log.error("Failed to release modifier after hold hotkey error: %s", release_error)
            raise ExecutionError(f"Failed to start hold hotkey {modifier} + {key}: {e}") from e

        self._active_hold_session = HoldHotkeySession(
            modifier=modifier,
            key=key,
            repeat_interval=repeat_interval,
            last_press_at=time.monotonic(),
        )
