"""
Unit tests for resources.lib.utils.language.

LanguagePreferences.from_args is the single place reading language/filter
settings from the addon args.
"""

import copy
import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace
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


# Season item of series G24H1N3MP (Mushoku Tensei) as listed by the seasons response in the Kodi log 2026-10-04.
MUSHOKU_SEASON_ITEM = {
    "id": "GS00374452DEDE",
    "series_id": "G24H1N3MP",
    "title": "Mushoku Tensei: Jobless Reincarnation",
    "audio_locale": "de-DE",
    "versions": [
        {"audio_locale": "ja-JP", "guid": "GS00374452JAJP", "original": True, "variant": ""},
        {"audio_locale": "en-US", "guid": "GS00374452ENUS", "original": False, "variant": ""},
        {"audio_locale": "es-419", "guid": "GS00374452ES419", "original": False, "variant": ""},
        {"audio_locale": "pt-BR", "guid": "GS00374452PTBR", "original": False, "variant": ""},
        {"audio_locale": "es-ES", "guid": "GS00374452ESES", "original": False, "variant": ""},
        {"audio_locale": "fr-FR", "guid": "GS00374452FRFR", "original": False, "variant": ""},
        {"audio_locale": "it-IT", "guid": "GS00374452ITIT", "original": False, "variant": ""},
        {"audio_locale": "de-DE", "guid": "GS00374452DEDE", "original": False, "variant": ""},
    ],
}

DECOY_SEASON_ITEM = {
    "id": "GS_OTHER_DEDE",
    "series_id": "G24H1N3MP",
    "title": "Another season",
    "audio_locale": "de-DE",
    "versions": [
        {"audio_locale": "ja-JP", "guid": "GS_OTHER_JAJP", "original": True, "variant": ""},
        {"audio_locale": "de-DE", "guid": "GS_OTHER_DEDE", "original": False, "variant": ""},
    ],
}


def _mushoku_items():
    return [copy.deepcopy(DECOY_SEASON_ITEM), copy.deepcopy(MUSHOKU_SEASON_ITEM)]


class TestWantedSeasonVersion:
    """Wanted version of the season an episode belongs to, decided by the season item's versions (decision 7.8)."""

    def test_mushoku_dub_settings_resolve_english_season_to_german_version(self):
        """Kodi log 2026-10-04: episode 13 only has ja/en, but the season has a de-DE version."""
        prefs = _prefs(show_dubs=True, show_dubs_fallback=True)

        result = language.wanted_season_version(_mushoku_items(), "GS00374452ENUS", prefs)

        assert result == ("GS00374452DEDE", "de-DE")

    def test_match_via_item_id(self):
        prefs = _prefs(show_dubs=True, show_dubs_fallback=True)

        result = language.wanted_season_version(_mushoku_items(), "GS00374452DEDE", prefs)

        assert result == ("GS00374452DEDE", "de-DE")

    def test_match_via_item_id_without_versions(self):
        items = [{"id": "OWN_SEASON", "title": "Season 1", "audio_locale": "de-DE"}]

        result = language.wanted_season_version(items, "OWN_SEASON", _prefs(show_dubs=True))

        assert result == ("OWN_SEASON", "de-DE")

    def test_fallback_dub_when_primary_missing(self):
        prefs = _prefs(subtitle="ru-RU", subtitle_fallback="fr-FR", show_dubs=True, show_dubs_fallback=True)

        result = language.wanted_season_version(_mushoku_items(), "GS00374452ENUS", prefs)

        assert result == ("GS00374452FRFR", "fr-FR")

    def test_filter_off_is_none(self):
        prefs = _prefs(filter_enabled=False, show_dubs=True, show_dubs_fallback=True)

        assert language.wanted_season_version(_mushoku_items(), "GS00374452ENUS", prefs) is None

    def test_unknown_season_id_is_none(self):
        prefs = _prefs(show_dubs=True, show_dubs_fallback=True)

        assert language.wanted_season_version(_mushoku_items(), "GS_UNKNOWN", prefs) is None

    def test_nothing_wanted_is_none(self):
        """ru-RU: none of the Mushoku versions has it (it-IT would be a wanted dub there)."""
        prefs = _prefs(subtitle="ru-RU", subtitle_fallback=None, show_dubs=True, show_dubs_fallback=True)

        assert language.wanted_season_version(_mushoku_items(), "GS00374452ENUS", prefs) is None

    def test_nothing_wanted_in_real_seasons_response_is_none(self, season_item):
        """seasons_V1 carries no it-IT version, so an it-IT dub-only setting wants nothing."""
        prefs = _prefs(subtitle="it-IT", subtitle_fallback=None, show_dubs=True)

        assert language.wanted_season_version([season_item], DE_ID, prefs) is None

    @pytest.mark.parametrize("items", [None, []])
    def test_no_items_is_none(self, items):
        assert language.wanted_season_version(items, "GS00374452ENUS", _prefs(show_dubs=True)) is None

    @pytest.mark.parametrize(
        ("fixture", "season_id"),
        [("seasons_V1", DE_ID), ("seasons_V1", EN_ID), ("seasons_V2", JA_ID), ("seasons_V2", DE_ID)],
    )
    def test_standard_settings_resolve_to_original(self, fixture, season_id):
        """Real season items carry subtitle_locales with de-DE, so show_subs wants the ja original."""
        items = _load_version_response(fixture)["data"]

        result = language.wanted_season_version(items, season_id, _prefs(show_subs=True))

        assert result == (JA_ID, "ja-JP")

    def test_default_settings_keep_own_allowed_dub_season(self, season_item):
        """settings.xml defaults: filter, dubs, fallback dubs and subs all on; the own de-DE season is allowed.

        Deliberate requirement change (Schritt 3d / Issue #136): an allowed own version stays. Before, the
        original came first by 4.1 order and the own de-DE season resolved to the ja-JP original.
        """
        prefs = _prefs(show_dubs=True, show_dubs_fallback=True, show_subs=True)

        assert language.wanted_season_version([season_item], DE_ID, prefs) == (DE_ID, "de-DE")

    def test_subs_and_dubs_keep_own_dub_season(self, season_item):
        """Schritt 3d / Issue #136: with subs and dubs on, the own de-DE season is the user's choice."""
        prefs = _prefs(show_dubs=True, show_subs=True)

        assert language.wanted_season_version([season_item], DE_ID, prefs) == (DE_ID, "de-DE")

    def test_subs_and_dubs_keep_own_original_season(self, season_item):
        prefs = _prefs(show_dubs=True, show_subs=True)

        assert language.wanted_season_version([season_item], JA_ID, prefs) == (JA_ID, "ja-JP")

    def test_subs_and_dubs_own_not_allowed_season_resolves_to_primary_dub(self, season_item):
        """Own en-US is not allowed (no fallback dubs), so the primary dub wins over the original."""
        prefs = _prefs(show_dubs=True, show_subs=True)

        assert language.wanted_season_version([season_item], EN_ID, prefs) == (DE_ID, "de-DE")

    def test_input_items_are_not_mutated(self):
        items = _mushoku_items()
        before = copy.deepcopy(items)

        language.wanted_season_version(items, "GS00374452ENUS", _prefs(show_dubs=True))

        assert items == before


def test_episode_target_is_removed():
    """Decision 7.8: the season target is decided by the season's versions, not the episode's."""
    assert not hasattr(language, "episode_target")


class TestDefaultEpisodeAudio:
    """Audio locale for old season_view URLs without audio_locale; never the account language."""

    def test_filter_off_is_none(self):
        assert language.default_episode_audio(_prefs(filter_enabled=False, show_dubs=True)) is None

    def test_show_dubs_returns_primary(self):
        assert language.default_episode_audio(_prefs(show_dubs=True, show_dubs_fallback=True)) == "de-DE"

    def test_fallback_dubs_only_returns_fallback(self):
        assert language.default_episode_audio(_prefs(show_dubs_fallback=True)) == "en-US"

    def test_fallback_dubs_without_fallback_language_is_none(self):
        assert language.default_episode_audio(_prefs(subtitle_fallback=None, show_dubs_fallback=True)) is None

    def test_subs_only_is_none(self):
        assert language.default_episode_audio(_prefs(show_subs=True)) is None

    def test_no_flags_is_none(self):
        assert language.default_episode_audio(_prefs()) is None


WANTED_SUBS = ["de-DE", "en-US"]
DUBS_ONLY = {"show_dubs": True, "show_dubs_fallback": True}
SUBS_AND_DUBS = {"show_dubs": True, "show_subs": True}


def _pick_variants(*audio_locales):
    """Variants keyed by audio locale; ja-JP is the original, all carry de-DE/en-US subtitles."""
    return {
        locale: _variant(locale, locale == "ja-JP", subtitle_locales=list(WANTED_SUBS), is_subbed=True)
        for locale in audio_locales
    }


class TestPickVersion:
    """Rule of Schritt 3d (Issue #136): keep an allowed own version, else primary dub, fallback dub, original."""

    def test_dubs_only_own_fallback_dub_switches_to_present_primary_dub(self):
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), "en-US", _prefs(**DUBS_ONLY))

        assert result == variants["de-DE"]

    def test_dubs_only_own_fallback_dub_without_primary_dub_is_kept(self):
        variants = _pick_variants("ja-JP", "en-US")

        result = language.pick_version(list(variants.values()), "en-US", _prefs(**DUBS_ONLY))

        assert result == variants["en-US"]

    def test_dubs_only_own_primary_dub_is_kept(self):
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), "de-DE", _prefs(**DUBS_ONLY))

        assert result == variants["de-DE"]

    def test_own_fallback_dub_is_kept_when_primary_dub_is_present_but_not_allowed(self):
        """Only fallback dubs on: de-DE exists but is not allowed, so the exception does not apply."""
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), "en-US", _prefs(show_dubs_fallback=True))

        assert result == variants["en-US"]

    def test_subs_and_dubs_own_original_is_kept(self):
        """Issue #136: a simulcast watched in the original stays original although the dub exists."""
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), "ja-JP", _prefs(**SUBS_AND_DUBS))

        assert result == variants["ja-JP"]

    def test_subs_and_dubs_own_primary_dub_is_kept(self):
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), "de-DE", _prefs(**SUBS_AND_DUBS))

        assert result == variants["de-DE"]

    def test_subs_and_dubs_own_not_allowed_switches_to_primary_dub(self):
        """en-US is not allowed without fallback dubs; the primary dub comes before the original."""
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), "en-US", _prefs(**SUBS_AND_DUBS))

        assert result == variants["de-DE"]

    def test_subs_and_dubs_own_not_allowed_without_primary_dub_switches_to_original(self):
        variants = _pick_variants("ja-JP", "en-US")

        result = language.pick_version(list(variants.values()), "en-US", _prefs(**SUBS_AND_DUBS))

        assert result == variants["ja-JP"]

    def test_subs_only_own_dub_switches_to_original(self):
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), "en-US", _prefs(show_subs=True))

        assert result == variants["ja-JP"]

    def test_own_not_allowed_without_primary_dub_switches_to_fallback_dub(self):
        variants = _pick_variants("ja-JP", "en-US")

        result = language.pick_version(list(variants.values()), "ja-JP", _prefs(**DUBS_ONLY))

        assert result == variants["en-US"]

    def test_own_not_allowed_with_primary_dub_present_but_not_allowed_switches_to_fallback_dub(self):
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), "ja-JP", _prefs(show_dubs_fallback=True))

        assert result == variants["en-US"]

    @pytest.mark.parametrize("own_audio_locale", ["it-IT", None])
    def test_own_not_in_variants_counts_as_not_allowed(self, own_audio_locale):
        variants = _pick_variants("ja-JP", "en-US", "de-DE")

        result = language.pick_version(list(variants.values()), own_audio_locale, _prefs(**DUBS_ONLY))

        assert result == variants["de-DE"]

    def test_filter_off_is_none(self):
        variants = _pick_variants("ja-JP", "en-US", "de-DE")
        prefs = _prefs(filter_enabled=False, **DUBS_ONLY)

        assert language.pick_version(list(variants.values()), "en-US", prefs) is None

    def test_nothing_allowed_is_none(self):
        variants = _pick_variants("ja-JP", "en-US", "de-DE")
        prefs = _prefs(subtitle="ru-RU", subtitle_fallback=None, show_dubs=True)

        assert language.pick_version(list(variants.values()), "en-US", prefs) is None

    def test_no_variants_is_none(self):
        assert language.pick_version([], "en-US", _prefs(**DUBS_ONLY)) is None

    def test_variants_are_not_mutated(self):
        variants = list(_pick_variants("ja-JP", "en-US", "de-DE").values())
        before = copy.deepcopy(variants)

        language.pick_version(variants, "en-US", _prefs(**SUBS_AND_DUBS))

        assert variants == before


def _watchlist_episode_meta():
    return _load_version_fixture_item("watchlist_episode_item")["panel"]["episode_metadata"]


def _load_version_fixture_item(name):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return json.load(f)[name]


def _episode(versions, audio_locale, subtitle_locales=None, is_subbed=True):
    return SimpleNamespace(
        versions=versions,
        audio_locale=audio_locale,
        subtitle_locales=list(WANTED_SUBS) if subtitle_locales is None else subtitle_locales,
        is_subbed=is_subbed,
    )


def _episode_version(audio_locale, original=False, guid=True, media_guid=True):
    code = audio_locale.replace("-", "").upper()
    version = {"audio_locale": audio_locale, "original": original, "season_guid": f"GS_{code}", "variant": ""}
    if guid:
        version["guid"] = f"GE_{code}"
    if media_guid:
        version["media_guid"] = f"GE_{code}V"
    return version


class TestWantedEpisodeVersion:
    """Version a resume/queue entry should play (Schritt 3d); None when the own version stays."""

    def test_watchlist_item_with_dub_settings_switches_to_german_version(self):
        meta = _watchlist_episode_meta()
        episode = _episode(meta["versions"], meta["audio_locale"], meta["subtitle_locales"], meta["is_subbed"])

        result = language.wanted_episode_version(episode, _prefs(**DUBS_ONLY))

        assert result == meta["versions"][1]

    def test_watchlist_item_with_subs_and_dubs_keeps_own_original(self):
        meta = _watchlist_episode_meta()
        episode = _episode(meta["versions"], meta["audio_locale"], meta["subtitle_locales"], meta["is_subbed"])

        assert language.wanted_episode_version(episode, _prefs(**SUBS_AND_DUBS)) is None

    def test_filter_off_is_none(self):
        meta = _watchlist_episode_meta()
        episode = _episode(meta["versions"], meta["audio_locale"], meta["subtitle_locales"], meta["is_subbed"])

        assert language.wanted_episode_version(episode, _prefs(filter_enabled=False, **DUBS_ONLY)) is None

    def test_nothing_allowed_is_none(self):
        meta = _watchlist_episode_meta()
        episode = _episode(meta["versions"], meta["audio_locale"], meta["subtitle_locales"], meta["is_subbed"])
        prefs = _prefs(subtitle="ru-RU", subtitle_fallback=None, show_dubs=True)

        assert language.wanted_episode_version(episode, prefs) is None

    def test_own_allowed_version_is_none(self):
        versions = [_episode_version("ja-JP", original=True), _episode_version("de-DE")]

        assert language.wanted_episode_version(_episode(versions, "de-DE"), _prefs(**DUBS_ONLY)) is None

    def test_subs_only_own_dub_switches_to_original(self):
        versions = [_episode_version("ja-JP", original=True), _episode_version("de-DE")]

        result = language.wanted_episode_version(_episode(versions, "de-DE"), _prefs(show_subs=True))

        assert result == versions[0]

    def test_original_flag_comes_from_the_version_and_subtitles_from_the_episode(self):
        """Issue #51 edge case: empty subtitle locales on a subbed episode count as wanted subtitles."""
        versions = [_episode_version("zh-CN", original=True), _episode_version("en-US")]
        episode = _episode(versions, "en-US", subtitle_locales=[], is_subbed=True)

        result = language.wanted_episode_version(episode, _prefs(show_subs=True))

        assert result == versions[0]

    @pytest.mark.parametrize("missing", ["guid", "media_guid", "season_guid"])
    def test_versions_without_ids_are_ignored(self, missing):
        """de-DE lacks an id, so the fallback dub is chosen instead of the primary dub."""
        versions = [
            _episode_version("ja-JP", original=True),
            _episode_version("de-DE"),
            _episode_version("en-US"),
        ]
        del versions[1][missing]

        result = language.wanted_episode_version(_episode(versions, "ja-JP"), _prefs(**DUBS_ONLY))

        assert result == versions[2]

    def test_version_without_audio_locale_is_ignored(self):
        """The original lacks audio_locale, so a subs-only de-DE dub has no version to switch to and stays."""
        versions = [_episode_version("ja-JP", original=True), _episode_version("de-DE")]
        del versions[0]["audio_locale"]

        assert language.wanted_episode_version(_episode(versions, "de-DE"), _prefs(show_subs=True)) is None

    def test_only_wanted_version_without_media_guid_is_none(self):
        versions = [_episode_version("ja-JP", original=True), _episode_version("de-DE", media_guid=False)]

        assert language.wanted_episode_version(_episode(versions, "ja-JP"), _prefs(show_dubs=True)) is None

    def test_episode_without_versions_is_none(self):
        assert language.wanted_episode_version(_episode([], "ja-JP"), _prefs(**DUBS_ONLY)) is None

    def test_versions_are_not_mutated(self):
        meta = _watchlist_episode_meta()
        before = copy.deepcopy(meta["versions"])
        episode = _episode(meta["versions"], meta["audio_locale"], meta["subtitle_locales"], meta["is_subbed"])

        language.wanted_episode_version(episode, _prefs(**DUBS_ONLY))

        assert meta["versions"] == before
