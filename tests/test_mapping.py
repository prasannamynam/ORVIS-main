"""
Unit tests for mapping/manager.py.

Uses a temporary JSON file per test so the real config/mappings.json is
never touched by the test suite.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mapping.manager import MappingError, MappingManager


@pytest.fixture
def manager(tmp_path):
    config_path = tmp_path / "mappings.json"
    return MappingManager(config_path=config_path)


def test_starts_empty(manager):
    assert manager.all_mappings() == {}


def test_add_mapping(manager):
    manager.add_mapping("V_SHAPE", r"C:\Automation\chrome.bat")
    entry = manager.get_action("V_SHAPE")
    assert entry is not None
    assert entry["path"] == r"C:\Automation\chrome.bat"
    assert entry["type"] == "batch"
    assert entry["enabled"] is True


def test_add_hotkey_mapping(manager):
    manager.add_mapping("NEXT_TAB", action_type="hotkey", keys=["ctrl", "tab"])
    entry = manager.get_action("NEXT_TAB")
    assert entry is not None
    assert entry["type"] == "hotkey"
    assert entry["keys"] == ["ctrl", "tab"]
    assert entry["enabled"] is True


def test_add_hold_hotkey_mapping(manager):
    manager.add_mapping("CLOSE_TAB", action_type="hold_hotkey", modifier="alt", key="tab")
    entry = manager.get_action("CLOSE_TAB")
    assert entry is not None
    assert entry["type"] == "hold_hotkey"
    assert entry["modifier"] == "alt"
    assert entry["key"] == "tab"
    assert entry["enabled"] is True


def test_edit_mapping(manager):
    manager.add_mapping("FIST", r"C:\Automation\music.bat")
    manager.edit_mapping("FIST", path=r"C:\Automation\music2.bat")
    entry = manager.get_action("FIST")
    assert entry["path"] == r"C:\Automation\music2.bat"


def test_edit_mapping_to_hotkey(manager):
    manager.add_mapping("V_SHAPE", r"C:\Automation\chrome.bat")
    manager.edit_mapping("V_SHAPE", action_type="hotkey", keys=["ctrl", "w"])
    entry = manager.get_action("V_SHAPE")
    assert entry["type"] == "hotkey"
    assert entry["keys"] == ["ctrl", "w"]
    assert "path" not in entry


def test_edit_mapping_to_hold_hotkey(manager):
    manager.add_mapping("V_SHAPE", r"C:\Automation\chrome.bat")
    manager.edit_mapping("V_SHAPE", action_type="hold_hotkey", modifier="alt", key="tab")
    entry = manager.get_action("V_SHAPE")
    assert entry["type"] == "hold_hotkey"
    assert entry["modifier"] == "alt"
    assert entry["key"] == "tab"
    assert "path" not in entry


def test_edit_nonexistent_raises(manager):
    with pytest.raises(MappingError):
        manager.edit_mapping("OPEN_PALM", path=r"C:\x.bat")


def test_delete_mapping(manager):
    manager.add_mapping("THUMBS_UP", r"C:\Automation\vscode.bat")
    manager.delete_mapping("THUMBS_UP")
    assert manager.get_action("THUMBS_UP") is None


def test_disabled_mapping_not_returned(manager):
    manager.add_mapping("V_SHAPE", r"C:\Automation\chrome.bat")
    manager.set_enabled("V_SHAPE", False)
    assert manager.get_action("V_SHAPE") is None
    # But it still exists in the full listing.
    assert "V_SHAPE" in manager.all_mappings()


def test_persistence_across_instances(tmp_path):
    config_path = tmp_path / "mappings.json"
    m1 = MappingManager(config_path=config_path)
    m1.add_mapping("FIST", r"C:\Automation\music.bat")

    m2 = MappingManager(config_path=config_path)
    assert m2.get_action("FIST")["path"] == r"C:\Automation\music.bat"
