"""
mapping/manager.py

Responsible for:
- Loading mappings.json
- Saving mappings
- Adding mappings
- Editing mappings
- Deleting mappings
- Finding the action associated with a gesture

The recognizer never sees this module and this module never sees the
recognizer — the mapping is the ONLY place gesture-to-action knowledge lives.

Schema (V1):
{
    "GESTURE_NAME": {
        "type": "batch",
        "path": "C:\\Automation\\example.bat",
        "enabled": true
    },
    "NEXT_TAB": {
        "type": "hotkey",
        "keys": ["ctrl", "tab"],
        "enabled": true
    },
    "ALT_TAB": {
        "type": "hold_hotkey",
        "modifier": "alt",
        "key": "tab",
        "enabled": true
    },
    ...
}

"type" is intentionally small and explicit: ORVIX currently supports
"batch", "hotkey", and "hold_hotkey" entries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from utils.constants import (
    ACTION_BATCH,
    ACTION_HOLD_HOTKEY,
    ACTION_HOTKEY,
    CONFIG_PATH,
)
from utils.logger import get_logger

log = get_logger("mapping.manager")

DEFAULT_ACTION_TYPE = "batch"
SUPPORTED_ACTION_TYPES = {
    ACTION_BATCH,
    ACTION_HOTKEY,
    ACTION_HOLD_HOTKEY,
}


class MappingError(RuntimeError):
    pass


class MappingManager:
    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = Path(config_path)
        self._mappings: Dict[str, dict] = {}
        self.load()

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def load(self) -> None:
        if not self.config_path.exists():
            log.info("No mappings file at %s yet; starting empty.", self.config_path)
            self._mappings = {}
            self._save_raw()
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._mappings = json.load(f)
            log.info("Loaded %d mapping(s) from %s", len(self._mappings), self.config_path)
        except (json.JSONDecodeError, OSError) as e:
            log.error("Failed to load mappings.json: %s", e)
            raise MappingError(f"Could not read mappings file: {e}") from e

    def _save_raw(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._mappings, f, indent=4)
        except OSError as e:
            log.error("Failed to save mappings.json: %s", e)
            raise MappingError(f"Could not write mappings file: {e}") from e

    def save(self) -> None:
        self._save_raw()
        log.info("Saved %d mapping(s) to %s", len(self._mappings), self.config_path)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_mapping(
        self,
        gesture: str,
        path: Optional[str] = None,
        action_type: str = DEFAULT_ACTION_TYPE,
        enabled: bool = True,
        keys: Optional[list[str]] = None,
        modifier: Optional[str] = None,
        key: Optional[str] = None,
    ) -> None:
        self._validate_action_type(action_type)

        entry = {
            "type": action_type,
            "enabled": enabled,
        }

        if action_type == ACTION_HOTKEY:
            if keys is not None:
                entry["keys"] = keys
        elif action_type == ACTION_HOLD_HOTKEY:
            if modifier is not None:
                entry["modifier"] = modifier
            if key is not None:
                entry["key"] = key
        else:
            if path is not None:
                entry["path"] = path

        self._mappings[gesture] = entry
        self.save()
        log.info("Added mapping: %s (%s)", gesture, action_type)

    def edit_mapping(
        self,
        gesture: str,
        path: Optional[str] = None,
        action_type: Optional[str] = None,
        enabled: Optional[bool] = None,
        keys: Optional[list[str]] = None,
        modifier: Optional[str] = None,
        key: Optional[str] = None,
    ) -> None:
        if gesture not in self._mappings:
            raise MappingError(f"No mapping exists for gesture '{gesture}'")

        entry = self._mappings[gesture]

        if path is not None:
            entry["path"] = path
        if action_type is not None:
            self._validate_action_type(action_type)
            entry["type"] = action_type
            if action_type == ACTION_HOTKEY:
                entry.pop("path", None)
                entry.pop("modifier", None)
                entry.pop("key", None)
            elif action_type == ACTION_HOLD_HOTKEY:
                entry.pop("path", None)
                entry.pop("keys", None)
            elif action_type == ACTION_BATCH:
                entry.pop("keys", None)
                entry.pop("modifier", None)
                entry.pop("key", None)
        if enabled is not None:
            entry["enabled"] = enabled
        if keys is not None:
            entry["keys"] = keys
            if entry.get("type") == ACTION_HOTKEY:
                entry.pop("path", None)
        if modifier is not None:
            entry["modifier"] = modifier
            if entry.get("type") == ACTION_HOLD_HOTKEY:
                entry.pop("keys", None)
                entry.pop("path", None)
        if key is not None:
            entry["key"] = key
            if entry.get("type") == ACTION_HOLD_HOTKEY:
                entry.pop("keys", None)
                entry.pop("path", None)

        self.save()
        log.info("Edited mapping for %s", gesture)

    def delete_mapping(self, gesture: str) -> None:
        if gesture in self._mappings:
            del self._mappings[gesture]
            self.save()
            log.info("Deleted mapping for %s", gesture)
        else:
            log.warning("Attempted to delete non-existent mapping for %s", gesture)

    def set_enabled(self, gesture: str, enabled: bool) -> None:
        self.edit_mapping(gesture, enabled=enabled)

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_action(self, gesture: str) -> Optional[dict]:
        """Returns the mapping entry for a gesture if it exists AND is enabled."""
        entry = self._mappings.get(gesture)
        if entry is None:
            return None
        if not entry.get("enabled", True):
            return None
        return entry

    def all_mappings(self) -> Dict[str, dict]:
        return dict(self._mappings)

    @staticmethod
    def _validate_action_type(action_type: str) -> None:
        if action_type not in SUPPORTED_ACTION_TYPES:
            raise MappingError(f"Unsupported action type: '{action_type}'")
