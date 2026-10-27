"""Unit tests for SkipModalDialog (UI only: reports the user's choice via return_value)."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

GUI_PATH = Path(__file__).resolve().parents[2] / "resources" / "lib" / "gui.py"
MODULE_NAME = "resources.lib._gui_under_test"  # package context for relative lazy imports in gui.py


class FakeWindowXMLDialog:
    def __init__(self, *args):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


@pytest.fixture
def gui_module(monkeypatch):
    fake_xbmcgui = MagicMock()
    fake_xbmcgui.WindowXMLDialog = FakeWindowXMLDialog
    monkeypatch.setitem(sys.modules, "xbmcgui", fake_xbmcgui)
    spec = importlib.util.spec_from_file_location(MODULE_NAME, GUI_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_dialog(gui_module, **overrides):
    """Single place to construct the dialog."""
    kwargs = {"label": "Skip Intro"}
    kwargs.update(overrides)
    return gui_module.SkipModalDialog("plugin-video-crunchyroll-skip.xml", "/addon/path", "default", "1080i", **kwargs)


def test_dialog_constructs_without_seek_time_and_content_id(gui_module):
    dialog = make_dialog(gui_module)

    assert dialog.label == "Skip Intro"


def test_click_on_skip_button_sets_return_value_and_closes(gui_module):
    dialog = make_dialog(gui_module)

    dialog.onClick(1000)

    assert dialog.return_value is True
    assert dialog.close_calls == 1


def test_click_on_other_control_does_nothing(gui_module):
    dialog = make_dialog(gui_module)

    dialog.onClick(999)

    assert not hasattr(dialog, "return_value")
    assert dialog.close_calls == 0


def test_exit_action_closes_without_result(gui_module):
    dialog = make_dialog(gui_module)
    action = MagicMock()
    action.getId.return_value = gui_module.ACTION_NAV_BACK

    dialog.onAction(action)

    assert dialog.close_calls == 1
    assert not hasattr(dialog, "return_value")
