"""
Tests for utils.get_listables_from_response type detection and DTO mapping.

Covers the migration of seasons/episodes to the content/v2 API, where items no
longer carry a type identifier (__class__/type) and the caller must pass an
explicit item_type_hint. Mixed lists (browse) must keep auto-detecting per item.
"""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from resources.lib.models.content import EpisodeData, SeasonData, SeriesData
from resources.lib.utils.api_data import get_listables_from_response


@pytest.fixture
def listable_args():
    args = MagicMock()
    args.addon.getSetting.return_value = "false"
    return args


def load_captured_response(name):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "captured_responses.json") as f:
        return json.load(f)[name]


def get_list(response):
    return response.get("data") or response.get("items") or []


class TestTypeHint:
    """item_type_hint resolves the type when items carry no identifier"""

    def test_seasons_mapped_with_hint(self, listable_args):
        seasons = get_list(load_captured_response("seasons_response"))

        listables = get_listables_from_response(seasons, item_type_hint="season", args=listable_args)

        assert len(listables) == len(seasons)
        assert all(isinstance(item, SeasonData) for item in listables)

    def test_episodes_mapped_with_hint(self, listable_args):
        episodes = get_list(load_captured_response("episodes_response"))

        listables = get_listables_from_response(episodes, item_type_hint="episode", args=listable_args)

        assert len(listables) == len(episodes)
        assert all(isinstance(item, EpisodeData) for item in listables)

    def test_seasons_without_hint_are_skipped(self, listable_args):
        """No type identifier and no hint -> item cannot be mapped"""
        seasons = get_list(load_captured_response("seasons_response"))

        listables = get_listables_from_response(seasons, args=listable_args)

        assert listables == []

    def test_per_item_type_wins_over_hint(self, listable_args):
        """A present type field must take precedence over the hint"""
        item = {"type": "series", "id": "X", "title": "T", "slug_title": "t"}

        listables = get_listables_from_response([item], item_type_hint="episode", args=listable_args)

        assert len(listables) == 1
        assert isinstance(listables[0], SeriesData)


class TestMixedListAutoDetection:
    """browse/search/watchlist still carry type identifiers and must not regress"""

    def test_browse_auto_detected_without_hint(self, listable_args):
        browse = get_list(load_captured_response("browse_response"))

        listables = get_listables_from_response(browse, args=listable_args)

        assert len(listables) > 0


class TestSeasonMapping:
    """SeasonData field mapping against new content/v2 data"""

    def test_season_fields(self):
        season_raw = get_list(load_captured_response("seasons_response"))[0]

        season = SeasonData(season_raw)

        assert season.id == season_raw["id"]
        assert season.title == season_raw["title"]
        assert season.series_id == season_raw["series_id"]
        assert season.season_id == season_raw["id"]
        assert season.season == season_raw["season_number"]

    def test_playcount_for_complete_season(self):
        season = SeasonData({"id": "S", "title": "T", "season_number": 1, "is_complete": True})

        assert season.playcount == 1

    def test_playcount_for_incomplete_season(self):
        season = SeasonData({"id": "S", "title": "T", "season_number": 1, "is_complete": False})

        assert season.playcount == 0

    def test_playcount_when_is_complete_missing(self):
        season = SeasonData({"id": "S", "title": "T", "season_number": 1})

        assert season.playcount == 0


class TestEpisodeMapping:
    """EpisodeData field mapping against new content/v2 data"""

    def test_episode_fields(self):
        episode_raw = get_list(load_captured_response("episodes_response"))[0]

        episode = EpisodeData(episode_raw)

        assert episode.id == episode_raw["id"]
        assert episode.episode_id == episode_raw["id"]
        assert episode.tvshowtitle == episode_raw["series_title"]
        assert episode.season == episode_raw["season_number"]
        assert episode.episode == episode_raw["episode_number"]
        assert episode.series_id == episode_raw["series_id"]
        assert episode.season_id == episode_raw["season_id"]
        assert episode.duration == int(episode_raw["duration_ms"] / 1000)

    def test_episode_stream_id_from_streams_link(self):
        """New data has no __links__; stream id must come from streams_link"""
        episode_raw = get_list(load_captured_response("episodes_response"))[0]
        assert "__links__" not in episode_raw
        assert "streams_link" in episode_raw

        episode = EpisodeData(episode_raw)

        assert episode.stream_id and episode.stream_id in episode_raw["streams_link"]


def load_version_season():
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return json.load(f)["seasons_V1"]["response"]["data"][0]


class TestSeasonAudioLocale:
    """SeasonData carries the audio locale of its version"""

    def test_audio_locale_attribute(self):
        season = SeasonData(load_version_season())

        assert season.audio_locale == "de-DE"

    def test_audio_locale_in_info(self):
        season = SeasonData(load_version_season())

        assert season.get_info()["audio_locale"] == "de-DE"

    def test_audio_locale_missing_is_none(self):
        season = SeasonData({"id": "S", "title": "T", "season_number": 1})

        assert season.audio_locale is None


class TestSeasonsNotFiltered:
    """Season selection happens before mapping; get_listables_from_response no longer filters seasons"""

    @pytest.fixture
    def filtering_args(self):
        args = MagicMock()
        args.addon.getSetting.return_value = "true"
        args.subtitle = "it-IT"
        args.subtitle_fallback = None
        return args

    def test_non_matching_season_is_still_mapped(self, filtering_args):
        season_raw = load_version_season()

        listables = get_listables_from_response([season_raw], item_type_hint="season", args=filtering_args)

        assert [item.id for item in listables] == [season_raw["id"]]
        assert isinstance(listables[0], SeasonData)

    def test_versions_are_not_expanded(self, filtering_args):
        season_raw = load_version_season()

        listables = get_listables_from_response([season_raw], item_type_hint="season", args=filtering_args)

        assert len(listables) == 1
        assert listables[0].title == "Season 1"

    def test_expand_versions_kwarg_is_rejected(self, listable_args):
        with pytest.raises(TypeError):
            get_listables_from_response([], item_type_hint="season", args=listable_args, expand_versions=True)


def load_version_fixture(name):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return copy.deepcopy(json.load(f)[name])


LANGUAGE_KEYS = ("audio_locale", "versions", "subtitle_locales", "is_subbed")


class TestEpisodeLanguageAttributes:
    """EpisodeData exposes audio locale, versions and subtitle info of content/v2 and watchlist items"""

    def test_content_v2_episode(self):
        item = load_version_fixture("episodes_GY19CPGQ9_V3")["response"]["data"][0]

        episode = EpisodeData(item)

        assert episode.audio_locale == "de-DE"
        assert episode.versions == item["versions"]
        assert isinstance(episode.versions, list)
        assert episode.subtitle_locales == item["subtitle_locales"]
        assert episode.is_subbed is True

    def test_watchlist_episode(self):
        item = load_version_fixture("watchlist_episode_item")
        meta = item["panel"]["episode_metadata"]

        episode = EpisodeData(item)

        assert episode.audio_locale == "ja-JP"
        assert episode.versions == meta["versions"]
        assert [v["season_guid"] for v in episode.versions] == [
            "GS00380130JAJP",
            "GS00380130DEDE",
            "GS00380130ES419",
            "GS00380130PTBR",
        ]
        assert "de-DE" in episode.subtitle_locales
        assert "en-US" in episode.subtitle_locales
        assert episode.is_subbed is True

    def test_content_v2_episode_without_language_keys(self):
        item = load_version_fixture("episodes_GY19CPGQ9_V3")["response"]["data"][0]
        for key in LANGUAGE_KEYS:
            item.pop(key)

        episode = EpisodeData(item)

        assert episode.audio_locale is None
        assert episode.versions == []
        assert episode.subtitle_locales == []
        assert episode.is_subbed is False

    def test_watchlist_episode_without_language_keys(self):
        item = load_version_fixture("watchlist_episode_item")
        for key in LANGUAGE_KEYS:
            item["panel"]["episode_metadata"].pop(key)

        episode = EpisodeData(item)

        assert episode.audio_locale is None
        assert episode.versions == []
        assert episode.subtitle_locales == []
        assert episode.is_subbed is False


class TestEpisodeUseVersion:
    """EpisodeData.use_version switches a listed episode to another version (Schritt 3d)."""

    @pytest.fixture
    def episode_and_version(self):
        item = load_version_fixture("watchlist_episode_item")
        episode = EpisodeData(item)
        episode.playhead = int(episode.duration * 0.95)
        episode.recalc_playcount()
        version = item["panel"]["episode_metadata"]["versions"][1]
        assert episode.id == "GE00380136JAJP"
        assert episode.stream_id == "GE00380136JAJPV"
        assert episode.playhead > 0
        assert episode.playcount == 1
        return episode, version

    def test_switches_ids_audio_and_season(self, episode_and_version):
        episode, version = episode_and_version

        episode.use_version(version)

        assert episode.id == "GE00380136DEDE"
        assert episode.stream_id == "GE00380136DEDEV"
        assert episode.audio_locale == "de-DE"
        assert episode.season_id == "GS00380130DEDE"

    def test_switches_episode_id_used_by_the_play_url(self, episode_and_version):
        """Beyond the written contract: get_info()['episode_id'] builds the video_episode_play URL."""
        episode, version = episode_and_version

        episode.use_version(version)

        assert episode.episode_id == "GE00380136DEDE"
        info = episode.get_info()
        assert info["episode_id"] == "GE00380136DEDE"
        assert info["stream_id"] == "GE00380136DEDEV"
        assert info["season_id"] == "GS00380130DEDE"

    def test_resets_progress_of_the_old_id(self, episode_and_version):
        """Playhead and playcount belong to the old id; view.complement_listables refetches them for the new id."""
        episode, version = episode_and_version

        episode.use_version(version)

        assert episode.playhead == 0
        assert episode.playcount == 0
        assert episode.get_info()["playhead"] == 0
        assert episode.get_info()["playcount"] == 0

    def test_keeps_other_attributes(self, episode_and_version):
        """Playhead is no longer kept (review 2026-10-05): progress of the old id must not show for the new id."""
        episode, version = episode_and_version
        before = {
            key: getattr(episode, key)
            for key in ("title", "title_unformatted", "duration", "series_id", "season", "episode")
        }
        versions_before = copy.deepcopy(episode.versions)

        episode.use_version(version)

        assert {key: getattr(episode, key) for key in before} == before
        assert episode.versions == versions_before
