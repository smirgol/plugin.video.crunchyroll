"""
Unit tests for resources.lib.utils.language.

LanguagePreferences.from_args is the single place reading language/filter
settings from the addon args.
"""

import copy
import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import resources.lib.utils.language as language
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


# --- Season versions (pure functions in resources.lib.utils.language) ---------------------------------------------

JA_ID = "GYE5CQNJ2"
ZH_ID = "GR75CDJPE"
ES_ID = "GR9PC2GZ8"
PT_ID = "G6X0C4Z10"
FR_ID = "GR49C78K8"
DE_ID = "GY19CPGQ9"
EN_ID = "GRJQC1EN0"


def _load_version_response(name):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return json.load(f)[name]["response"]


@pytest.fixture
def season_item():
    """The de-DE season item of seasons_V1, carrying all 7 versions."""
    return _load_version_response("seasons_V1")["data"][0]


def _prefs(
    subtitle="de-DE",
    subtitle_fallback="en-US",
    filter_enabled=True,
    show_dubs=False,
    show_dubs_fallback=False,
    show_subs=False,
):
    return LanguagePreferences(
        subtitle=subtitle,
        subtitle_fallback=subtitle_fallback,
        filter_enabled=filter_enabled,
        show_dubs=show_dubs,
        show_dubs_fallback=show_dubs_fallback,
        show_subs=show_subs,
    )


def _variant(audio_locale, original, subtitle_locales=None, is_subbed=False, title="Season 1"):
    return {
        "id": f"ID-{audio_locale}",
        "title": title,
        "audio_locale": audio_locale,
        "original": original,
        "subtitle_locales": [] if subtitle_locales is None else subtitle_locales,
        "is_subbed": is_subbed,
    }


class TestSeasonVersions:
    def test_one_variant_per_version_in_versions_order(self, season_item):
        variants = language.season_versions(season_item)

        assert [v["id"] for v in variants] == [JA_ID, ZH_ID, ES_ID, PT_ID, FR_ID, DE_ID, EN_ID]
        assert [v["audio_locale"] for v in variants] == [
            "ja-JP",
            "zh-CN",
            "es-419",
            "pt-BR",
            "fr-FR",
            "de-DE",
            "en-US",
        ]
        assert [v["original"] for v in variants] == [True, False, False, False, False, False, False]

    def test_other_fields_are_copied(self, season_item):
        variants = language.season_versions(season_item)

        for variant in variants:
            assert variant["title"] == season_item["title"]
            assert variant["subtitle_locales"] == season_item["subtitle_locales"]
            assert variant["series_id"] == season_item["series_id"]
            assert variant["is_subbed"] == season_item["is_subbed"]

    def test_input_item_is_not_mutated(self, season_item):
        before = copy.deepcopy(season_item)

        variants = language.season_versions(season_item)

        assert season_item == before
        assert all(variant is not season_item for variant in variants)

    def test_empty_versions_yields_single_variant(self):
        item = {"id": "S1", "title": "Season 1", "audio_locale": "de-DE", "versions": []}

        variants = language.season_versions(item)

        assert len(variants) == 1
        assert variants[0]["id"] == "S1"
        assert variants[0]["audio_locale"] == "de-DE"
        assert variants[0]["original"] is False

    @pytest.mark.parametrize(
        ("audio_locale", "expected_original"),
        [("ja-JP", True), ("zh-CN", True), ("de-DE", False)],
    )
    def test_item_without_versions_uses_locale_originality(self, audio_locale, expected_original):
        item = {"id": "S1", "title": "Season 1", "audio_locale": audio_locale, "series_id": "SER"}

        variants = language.season_versions(item)

        assert len(variants) == 1
        assert variants[0]["id"] == "S1"
        assert variants[0]["series_id"] == "SER"
        assert variants[0]["original"] is expected_original
        assert "original" not in item


class TestHasWantedSubtitles:
    def test_empty_locales_and_subbed_counts_as_wanted_issue_51(self):
        assert language.has_wanted_subtitles([], True, _prefs()) is True

    def test_empty_locales_and_not_subbed_is_not_wanted(self):
        assert language.has_wanted_subtitles([], False, _prefs()) is False

    def test_primary_subtitle_matches(self):
        assert language.has_wanted_subtitles(["fr-FR", "de-DE"], False, _prefs()) is True

    def test_fallback_subtitle_matches(self):
        assert language.has_wanted_subtitles(["en-US"], False, _prefs()) is True

    @pytest.mark.parametrize("fallback", [None, ""])
    def test_unset_fallback_does_not_match(self, fallback):
        prefs = _prefs(subtitle="it-IT", subtitle_fallback=fallback)

        assert language.has_wanted_subtitles(["en-US", ""], False, prefs) is False

    def test_no_match(self):
        assert language.has_wanted_subtitles(["fr-FR", "es-ES"], True, _prefs()) is False


class TestIsVersionWanted:
    def test_filter_disabled_wants_everything(self):
        prefs = _prefs(filter_enabled=False)

        assert language.is_version_wanted(_variant("fr-FR", False), prefs) is True

    def test_primary_dub_wanted_with_show_dubs(self):
        assert language.is_version_wanted(_variant("de-DE", False), _prefs(show_dubs=True)) is True

    def test_primary_dub_not_wanted_without_show_dubs(self):
        prefs = _prefs(show_dubs_fallback=True, show_subs=True)

        assert language.is_version_wanted(_variant("de-DE", False, ["de-DE"]), prefs) is False

    def test_fallback_dub_wanted_with_show_dubs_fallback(self):
        assert language.is_version_wanted(_variant("en-US", False), _prefs(show_dubs_fallback=True)) is True

    def test_fallback_dub_not_wanted_with_only_show_dubs(self):
        assert language.is_version_wanted(_variant("en-US", False), _prefs(show_dubs=True)) is False

    def test_original_with_wanted_subs_and_show_subs(self):
        variant = _variant("ja-JP", True, ["de-DE"])

        assert language.is_version_wanted(variant, _prefs(show_subs=True)) is True

    def test_original_with_wanted_subs_without_show_subs(self):
        variant = _variant("ja-JP", True, ["de-DE"])

        assert language.is_version_wanted(variant, _prefs(show_dubs=True, show_dubs_fallback=True)) is False

    def test_non_original_chinese_version_not_wanted_with_show_subs(self):
        """Originality comes from versions[].original, not from the audio locale."""
        variant = _variant("zh-CN", False, ["de-DE"], is_subbed=True)

        assert language.is_version_wanted(variant, _prefs(show_subs=True)) is False

    def test_variant_without_subtitle_fields_is_not_subbed(self):
        variant = {"id": "X", "audio_locale": "ja-JP", "original": True}

        assert language.is_version_wanted(variant, _prefs(show_subs=True)) is False


class TestIsVersionWantedPortedFromFilterSeasons:
    """Moved from the former season-filter tests in test_utils_modules.py (that filter function is removed).

    Items have no ``versions``, so season_versions applies the fallback originality rule
    (ja-JP / zh-CN count as original).
    """

    @staticmethod
    def _wanted(item, prefs):
        return language.is_version_wanted(language.season_versions(item)[0], prefs)

    def test_main_audio_matches(self):
        assert self._wanted({"audio_locale": "de-DE"}, _prefs(show_dubs=True)) is True

    def test_japanese_with_fallback_subs(self):
        item = {"audio_locale": "ja-JP", "subtitle_locales": ["en-US"]}

        assert self._wanted(item, _prefs(show_subs=True)) is True

    def test_chinese_only_subbed_without_subtitle_locales(self):
        """Issue #51 edge case: zh-CN audio, empty subtitle_locales, is_subbed True."""
        item = {"audio_locale": "zh-CN", "subtitle_locales": [], "is_subbed": True}

        assert self._wanted(item, _prefs(show_subs=True)) is True

    def test_chinese_only_not_subbed_without_subtitle_locales(self):
        item = {"audio_locale": "zh-CN", "subtitle_locales": [], "is_subbed": False}

        assert self._wanted(item, _prefs(show_subs=True)) is False

    def test_subs_only_rejects_dub_season(self):
        item = {"audio_locale": "de-DE", "subtitle_locales": ["de-DE"]}

        assert self._wanted(item, _prefs(show_subs=True)) is False

    @pytest.mark.parametrize("fallback", [None, ""])
    def test_fallback_audio_without_fallback_language(self, fallback):
        prefs = _prefs(subtitle_fallback=fallback, show_dubs_fallback=True)

        assert self._wanted({"audio_locale": "en-US"}, prefs) is False

    def test_japanese_without_matching_subtitles(self):
        item = {"audio_locale": "ja-JP", "subtitle_locales": ["fr-FR"]}

        assert self._wanted(item, _prefs(show_subs=True)) is False

    def test_disabled_returns_true(self):
        item = {"audio_locale": "fr-FR", "subtitle_locales": []}

        assert self._wanted(item, _prefs(filter_enabled=False)) is True


class TestOrderVersions:
    def test_original_then_primary_then_fallback_then_rest_alphabetical(self):
        variants = [
            _variant("zh-CN", False),
            _variant("en-US", False),
            _variant("pt-BR", False),
            _variant("de-DE", False),
            _variant("ja-JP", True),
            _variant("es-419", False),
            _variant("fr-FR", False),
        ]

        ordered = language.order_versions(variants, _prefs())

        assert [v["audio_locale"] for v in ordered] == [
            "ja-JP",
            "de-DE",
            "en-US",
            "es-419",
            "fr-FR",
            "pt-BR",
            "zh-CN",
        ]

    def test_unset_fallback_sorts_former_fallback_alphabetically(self):
        variants = [_variant("zh-CN", False), _variant("en-US", False), _variant("de-DE", False)]

        ordered = language.order_versions(variants, _prefs(subtitle_fallback=None))

        assert [v["audio_locale"] for v in ordered] == ["de-DE", "en-US", "zh-CN"]

    def test_input_list_is_not_reordered(self):
        variants = [_variant("zh-CN", False), _variant("ja-JP", True)]

        language.order_versions(variants, _prefs())

        assert [v["audio_locale"] for v in variants] == ["zh-CN", "ja-JP"]


class TestLocaleCode:
    @pytest.mark.parametrize(
        ("locale", "expected"),
        [
            ("ja-JP", "JP"),
            ("de-DE", "DE"),
            ("en-US", "US"),
            ("pt-BR", "BR"),
            ("es-419", "ES-419"),
            ("ja", "JA"),
        ],
    )
    def test_locale_code(self, locale, expected):
        assert language.locale_code(locale) == expected


class TestVersionLabel:
    def test_original_with_primary_subtitle(self):
        variant = _variant("ja-JP", True, ["en-US", "de-DE"])

        assert language.version_label(variant, _prefs()) == "[JP Audio | DE Sub]"

    def test_original_with_only_fallback_subtitle(self):
        variant = _variant("ja-JP", True, ["fr-FR", "en-US"])

        assert language.version_label(variant, _prefs()) == "[JP Audio | US Sub]"

    def test_original_without_wanted_subtitles(self):
        variant = _variant("ja-JP", True, ["fr-FR"])

        assert language.version_label(variant, _prefs()) == "[JP Audio]"

    def test_dub(self):
        variant = _variant("de-DE", False, ["de-DE", "en-US"])

        assert language.version_label(variant, _prefs()) == "[DE Audio]"

    def test_dub_with_numeric_region(self):
        assert language.version_label(_variant("es-419", False), _prefs()) == "[ES-419 Audio]"


class TestSelectSeasonVersions:
    @staticmethod
    def _summary(variants):
        return [(v["id"], v["title"]) for v in variants]

    def test_filter_off_returns_all_versions_ordered_and_labelled(self, season_item):
        result = language.select_season_versions([season_item], _prefs(filter_enabled=False))

        assert self._summary(result) == [
            (JA_ID, "Season 1 [JP Audio | DE Sub]"),
            (DE_ID, "Season 1 [DE Audio]"),
            (EN_ID, "Season 1 [US Audio]"),
            (ES_ID, "Season 1 [ES-419 Audio]"),
            (FR_ID, "Season 1 [FR Audio]"),
            (PT_ID, "Season 1 [BR Audio]"),
            (ZH_ID, "Season 1 [CN Audio]"),
        ]

    def test_dub_settings(self, season_item):
        prefs = _prefs(show_dubs=True, show_dubs_fallback=True)

        result = language.select_season_versions([season_item], prefs)

        assert self._summary(result) == [
            (DE_ID, "Season 1 [DE Audio]"),
            (EN_ID, "Season 1 [US Audio]"),
        ]

    def test_subs_only_returns_original_without_label(self, season_item):
        result = language.select_season_versions([season_item], _prefs(show_subs=True))

        assert self._summary(result) == [(JA_ID, "Season 1")]

    def test_subs_and_primary_dub(self, season_item):
        prefs = _prefs(show_subs=True, show_dubs=True)

        result = language.select_season_versions([season_item], prefs)

        assert self._summary(result) == [
            (JA_ID, "Season 1 [JP Audio | DE Sub]"),
            (DE_ID, "Season 1 [DE Audio]"),
        ]

    def test_no_wanted_version_returns_empty(self, season_item):
        prefs = _prefs(subtitle="it-IT", subtitle_fallback=None, show_dubs=True)

        assert language.select_season_versions([season_item], prefs) == []

    @pytest.mark.parametrize("items", [None, []])
    def test_no_items_returns_empty(self, items):
        assert language.select_season_versions(items, _prefs()) == []

    def test_seasons_keep_api_order(self, season_item):
        season_a = copy.deepcopy(season_item)
        season_a["title"] = "Season A"
        season_b = {
            "id": "B-JA",
            "title": "Season B",
            "audio_locale": "ja-JP",
            "subtitle_locales": ["de-DE"],
            "is_subbed": True,
            "versions": [
                {"audio_locale": "de-DE", "guid": "B-DE", "original": False},
                {"audio_locale": "ja-JP", "guid": "B-JA", "original": True},
            ],
        }
        prefs = _prefs(show_subs=True, show_dubs=True)

        result = language.select_season_versions([season_a, season_b], prefs)

        assert self._summary(result) == [
            (JA_ID, "Season A [JP Audio | DE Sub]"),
            (DE_ID, "Season A [DE Audio]"),
            ("B-JA", "Season B [JP Audio | DE Sub]"),
            ("B-DE", "Season B [DE Audio]"),
        ]

    def test_input_items_are_not_mutated(self, season_item):
        before = copy.deepcopy(season_item)

        language.select_season_versions([season_item], _prefs(filter_enabled=False))

        assert season_item == before
