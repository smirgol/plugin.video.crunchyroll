"""
Tests for utils.get_listables_from_response type detection and DTO mapping.

Covers the migration of seasons/episodes to the content/v2 API, where items no
longer carry a type identifier (__class__/type) and the caller must pass an
explicit item_type_hint. Mixed lists (browse) must keep auto-detecting per item.
"""

import json
from pathlib import Path

from resources.lib.model import EpisodeData, SeasonData, SeriesData
from resources.lib.utils import get_listables_from_response


def load_captured_response(name):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "captured_responses.json") as f:
        return json.load(f)[name]


def get_list(response):
    return response.get("data") or response.get("items") or []


class TestTypeHint:
    """item_type_hint resolves the type when items carry no identifier"""

    def test_seasons_mapped_with_hint(self):
        seasons = get_list(load_captured_response("seasons_response"))

        listables = get_listables_from_response(seasons, item_type_hint="season")

        assert len(listables) == len(seasons)
        assert all(isinstance(item, SeasonData) for item in listables)

    def test_episodes_mapped_with_hint(self):
        episodes = get_list(load_captured_response("episodes_response"))

        listables = get_listables_from_response(episodes, item_type_hint="episode")

        assert len(listables) == len(episodes)
        assert all(isinstance(item, EpisodeData) for item in listables)

    def test_seasons_without_hint_are_skipped(self):
        """No type identifier and no hint -> item cannot be mapped"""
        seasons = get_list(load_captured_response("seasons_response"))

        listables = get_listables_from_response(seasons)

        assert listables == []

    def test_per_item_type_wins_over_hint(self):
        """A present type field must take precedence over the hint"""
        item = {"type": "series", "id": "X", "title": "T", "slug_title": "t"}

        listables = get_listables_from_response([item], item_type_hint="episode")

        assert len(listables) == 1
        assert isinstance(listables[0], SeriesData)


class TestMixedListAutoDetection:
    """browse/search/watchlist still carry type identifiers and must not regress"""

    def test_browse_auto_detected_without_hint(self):
        browse = get_list(load_captured_response("browse_response"))

        listables = get_listables_from_response(browse)

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
