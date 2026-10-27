"""
Checks for the next-episode dialog settings in resources/settings.xml.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

RESOURCES_DIR = Path(__file__).parent.parent.parent / "resources"
SETTINGS_FILE = RESOURCES_DIR / "settings.xml"
EN_GB_STRINGS = RESOURCES_DIR / "language" / "resource.language.en_gb" / "strings.po"

ENABLE_ID = "enable_next_episode_dialog"
COUNTDOWN_ID = "next_episode_countdown"


def _root():
    return ET.parse(SETTINGS_FILE).getroot()


def _setting(setting_id):
    return _root().find(f".//setting[@id='{setting_id}']")


def _playback_setting(setting_id):
    return _root().find(f".//category[@id='playback_options']//setting[@id='{setting_id}']")


def test_enable_next_episode_dialog_setting():
    setting = _setting(ENABLE_ID)

    assert setting is not None
    assert setting.get("type") == "boolean"
    assert setting.get("label") == "30500"
    assert setting.findtext("default") == "false"
    assert setting.find("control").get("type") == "toggle"
    assert _playback_setting(ENABLE_ID) is not None


def test_next_episode_countdown_setting():
    setting = _setting(COUNTDOWN_ID)

    assert setting is not None
    assert _playback_setting(COUNTDOWN_ID) is not None
    assert setting.get("type") == "integer"
    assert setting.get("label") == "30501"
    assert setting.findtext("default") == "15"
    assert setting.findtext("constraints/minimum") == "5"
    assert setting.findtext("constraints/step") == "5"
    assert setting.findtext("constraints/maximum") == "60"
    control = setting.find("control")
    assert control.get("type") == "slider"
    assert control.get("format") == "integer"


def test_next_episode_countdown_depends_on_enable():
    setting = _setting(COUNTDOWN_ID)

    assert setting is not None
    dependency = setting.find("dependencies/dependency")
    assert dependency is not None
    assert dependency.get("type") == "enable"
    assert dependency.get("setting") == ENABLE_ID
    assert (dependency.text or "").strip() == "true"


def test_next_episode_settings_follow_ask_before_skipping():
    group = _root().find(".//category[@id='playback_options']/group[@id='1']")

    assert group is not None
    ids = [setting.get("id") for setting in group.findall("setting")]
    assert "ask_before_skipping" in ids
    start = ids.index("ask_before_skipping")
    assert ids[start : start + 3] == ["ask_before_skipping", ENABLE_ID, COUNTDOWN_ID]


def test_next_episode_setting_labels_exist():
    content = EN_GB_STRINGS.read_text(encoding="utf-8")

    for string_id in (30500, 30501):
        assert re.search(rf'^msgctxt "#{string_id}"$', content, re.MULTILINE), f"#{string_id} missing in en_gb"
