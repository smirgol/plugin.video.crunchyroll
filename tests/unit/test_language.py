"""
Unit tests for resources.lib.utils.language.

LanguagePreferences.from_args is the single place reading language/filter
settings from the addon args.
"""

import dataclasses
from unittest.mock import MagicMock

import pytest

from resources.lib.utils.language import LanguagePreferences

SETTING_KEYS = (
    "filter_dubs_by_language",
    "show_dubs_by_language",
    "show_dubs_by_language_fallback",
    "show_subs_by_language",
)

FLAG_BY_SETTING = {
    "filter_dubs_by_language": "filter_enabled",
    "show_dubs_by_language": "show_dubs",
    "show_dubs_by_language_fallback": "show_dubs_fallback",
    "show_subs_by_language": "show_subs",
}


def _make_args(settings, subtitle="de-DE", subtitle_fallback="en-US"):
    args = MagicMock()
    args.addon = MagicMock()
    args.subtitle = subtitle
    args.subtitle_fallback = subtitle_fallback
    args.addon.getSetting.side_effect = lambda name: settings.get(name, "false")
    return args


class TestLanguagePreferencesFromArgs:
    def test_all_settings_true_maps_all_flags_and_languages(self):
        args = _make_args({key: "true" for key in SETTING_KEYS})

        prefs = LanguagePreferences.from_args(args)

        assert prefs.subtitle == "de-DE"
        assert prefs.subtitle_fallback == "en-US"
        assert prefs.filter_enabled is True
        assert prefs.show_dubs is True
        assert prefs.show_dubs_fallback is True
        assert prefs.show_subs is True

    def test_all_settings_false_maps_all_flags_false(self):
        args = _make_args({key: "false" for key in SETTING_KEYS})

        prefs = LanguagePreferences.from_args(args)

        assert prefs.filter_enabled is False
        assert prefs.show_dubs is False
        assert prefs.show_dubs_fallback is False
        assert prefs.show_subs is False

    @pytest.mark.parametrize("enabled_key", SETTING_KEYS)
    def test_each_flag_maps_from_its_own_setting(self, enabled_key):
        args = _make_args({enabled_key: "true"})

        prefs = LanguagePreferences.from_args(args)

        for key, flag in FLAG_BY_SETTING.items():
            assert getattr(prefs, flag) is (key == enabled_key), flag

    @pytest.mark.parametrize("value", ["True", "1", "", "TRUE", "yes"])
    def test_non_exact_true_strings_map_to_false(self, value):
        args = _make_args({key: value for key in SETTING_KEYS})

        prefs = LanguagePreferences.from_args(args)

        assert prefs.filter_enabled is False
        assert prefs.show_dubs is False
        assert prefs.show_dubs_fallback is False
        assert prefs.show_subs is False

    def test_subtitle_fallback_none_passes_through(self):
        args = _make_args({}, subtitle_fallback=None)

        prefs = LanguagePreferences.from_args(args)

        assert prefs.subtitle == "de-DE"
        assert prefs.subtitle_fallback is None

    def test_subtitle_fallback_empty_string_passes_through(self):
        args = _make_args({}, subtitle_fallback="")

        prefs = LanguagePreferences.from_args(args)

        assert prefs.subtitle_fallback == ""

    def test_instance_is_frozen(self):
        prefs = LanguagePreferences.from_args(_make_args({}))

        with pytest.raises(dataclasses.FrozenInstanceError):
            prefs.show_dubs = True
