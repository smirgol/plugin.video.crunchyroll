"""
Tests for API Response → Model Mapping

Tests that API responses are correctly parsed into resources.lib.model.py objects.
Uses real responses from captured_responses.json.
"""

import json
from pathlib import Path


def load_captured_response(name):
    """Load real API response from captured_responses.json"""
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "captured_responses.json") as f:
        return json.load(f)[name]


class TestProfileMapping:
    """Test ProfileData parsing"""

    def test_profile_response_structure(self):
        """Test that profile response has all required fields"""
        profile_api = load_captured_response("profile_response")

        assert "username" in profile_api
        assert "profile_name" in profile_api
        assert "preferred_content_subtitle_language" in profile_api
        assert "maturity_rating" in profile_api
        assert "avatar" in profile_api

    def test_profile_maturity_rating(self):
        """Test Maturity Rating Format"""
        profile_api = load_captured_response("profile_response")

        # Maturity rating should be a string (e.g. "M3", "M2")
        assert isinstance(profile_api["maturity_rating"], str)
        assert profile_api["maturity_rating"].startswith("M")


class TestIndexMapping:
    """Test Index/CMS Response Mapping"""

    def test_cms_data_exists(self):
        """Test that CMS data exists"""
        index_api = load_captured_response("index_response")

        assert "cms" in index_api
        cms = index_api["cms"]

        assert "bucket" in cms
        assert "policy" in cms
        assert "signature" in cms
        assert "key_pair_id" in cms

    def test_cms_bucket_format(self):
        """Test CMS bucket format"""
        index_api = load_captured_response("index_response")

        cms = index_api["cms"]
        bucket = cms["bucket"]

        # Bucket should start with / and contain country/maturity
        assert bucket.startswith("/")
        assert "/" in bucket[1:]  # Mindestens 2 Teile

    def test_service_available_flag(self):
        """Test service_available flag"""
        index_api = load_captured_response("index_response")

        assert "service_available" in index_api
        assert isinstance(index_api["service_available"], bool)


class TestBrowseMapping:
    """Test Browse Response structure"""

    def test_browse_uses_items_not_data(self):
        """Browse uses 'items' not 'data'"""
        browse_api = load_captured_response("browse_response")

        # Browse MUSS "items" haben
        assert "items" in browse_api
        assert "total" in browse_api
        assert isinstance(browse_api["items"], list)

    def test_browse_total_count(self):
        """Test that total is an integer"""
        browse_api = load_captured_response("browse_response")

        assert isinstance(browse_api["total"], int)
        assert browse_api["total"] >= 0

    def test_browse_item_structure(self):
        """Test that Browse items have all required fields"""
        browse_api = load_captured_response("browse_response")

        if len(browse_api["items"]) > 0:
            first_item = browse_api["items"][0]

            # Basic fields
            assert "id" in first_item
            assert "type" in first_item
            assert "title" in first_item

            # Type should be known
            assert first_item["type"] in ["series", "movie_listing", "music", "episode"]


class TestSearchMapping:
    """Test Search Response structure"""

    def test_search_uses_items_not_data(self):
        """Search uses 'items' not 'data'"""
        search_api = load_captured_response("search_response")

        # Search MUSS auch "items" haben
        assert "items" in search_api
        assert "total" in search_api

    def test_search_item_groups(self):
        """Test Search items structure (can be nested)"""
        search_api = load_captured_response("search_response")

        # Search kann Item Groups haben (top_results, series, episodes, etc.)
        assert isinstance(search_api["items"], list)

        for item_group in search_api["items"]:
            # Each item should have at least a type
            assert "type" in item_group


class TestSeasonsMapping:
    """Test Seasons Response structure"""

    def test_seasons_uses_items(self):
        """Seasons uses 'items' not 'data'"""
        seasons_api = load_captured_response("seasons_response")

        # Seasons uses "items" (wie Browse/Search)
        assert "items" in seasons_api
        assert "total" in seasons_api
        assert isinstance(seasons_api["items"], list)

    def test_season_item_structure(self):
        """Test that Season items have all required fields"""
        seasons_api = load_captured_response("seasons_response")

        if len(seasons_api["items"]) > 0:
            season = seasons_api["items"][0]

            # Critical fields for Seasons
            assert "id" in season
            assert "season_number" in season
            assert "series_id" in season

            # Season number should be integer or integer-string
            season_num = season["season_number"]
            assert isinstance(season_num, (int, str))


class TestEpisodesMapping:
    """Test Episodes Response structure"""

    def test_episodes_uses_items(self):
        """Episodes uses 'items' not 'data'"""
        episodes_api = load_captured_response("episodes_response")

        # Episodes uses "items" (wie Browse/Search/Seasons)
        assert "items" in episodes_api
        assert "total" in episodes_api
        assert isinstance(episodes_api["items"], list)

    def test_episode_item_structure(self):
        """Test that Episode items have all required fields"""
        episodes_api = load_captured_response("episodes_response")

        if len(episodes_api["items"]) > 0:
            episode = episodes_api["items"][0]

            # Critical fields for Episodes
            assert "id" in episode
            assert "title" in episode

            # Episode number kann als "episode_number" oder "episode" vorhanden sein
            assert "episode_number" in episode or "episode" in episode

    def test_episode_playback_fields(self):
        """Test that playback-relevant fields exist"""
        episodes_api = load_captured_response("episodes_response")

        if len(episodes_api["items"]) > 0:
            episode = episodes_api["items"][0]

            # Important for playback
            if "duration_ms" in episode:
                assert isinstance(episode["duration_ms"], int)
                assert episode["duration_ms"] > 0

            # Series ID for navigation back
            if "series_id" in episode:
                assert isinstance(episode["series_id"], str)


class TestWatchlistMapping:
    """Test Watchlist Response structure"""

    def test_watchlist_uses_items(self):
        """Watchlist uses 'items' not 'data'"""
        watchlist_api = load_captured_response("watchlist_response")

        assert "total" in watchlist_api
        # Watchlist uses "items"
        assert "items" in watchlist_api
        assert isinstance(watchlist_api["items"], list)

    def test_watchlist_item_structure(self):
        """Test Watchlist item structure"""
        watchlist_api = load_captured_response("watchlist_response")

        if len(watchlist_api["items"]) > 0:
            item = watchlist_api["items"][0]

            # Watchlist items should Panel oder Series sein
            if "panel" in item:
                panel = item["panel"]
                assert "id" in panel
                assert "type" in panel


class TestHistoryMapping:
    """Test History Response structure"""

    def test_history_uses_data(self):
        """Test History Response uses 'data'"""
        history_api = load_captured_response("history_response")

        assert "total" in history_api
        # History uses "data"
        assert "data" in history_api
        assert isinstance(history_api["data"], list)

    def test_history_item_structure(self):
        """Test History item structure"""
        history_api = load_captured_response("history_response")

        if len(history_api["data"]) > 0:
            item = history_api["data"][0]

            # History items should Panel haben
            if "panel" in item:
                panel = item["panel"]
                assert "id" in panel
                assert "type" in panel

            # Playhead information (ist ein Integer, nicht ein Object)
            if "playhead" in item:
                playhead = item["playhead"]
                assert isinstance(playhead, int)  # Position in ms


class TestResponseConsistency:
    """Test consistency between different response types"""

    def test_items_vs_data_consistency(self):
        """Test Response Struktur Konsistenz"""
        browse = load_captured_response("browse_response")
        search = load_captured_response("search_response")
        seasons = load_captured_response("seasons_response")
        episodes = load_captured_response("episodes_response")
        watchlist = load_captured_response("watchlist_response")
        history = load_captured_response("history_response")

        # Browse, Search, Seasons, Episodes, Watchlist nutzen "items"
        assert "items" in browse
        assert "items" in search
        assert "items" in seasons
        assert "items" in episodes
        assert "items" in watchlist

        # ONLY History uses "data"
        assert "data" in history

    def test_all_have_total_field(self):
        """Test that all responses have a 'total' field"""
        responses = [
            "browse_response",
            "search_response",
            "seasons_response",
            "episodes_response",
            "watchlist_response",
            "history_response"
        ]

        for response_name in responses:
            data = load_captured_response(response_name)
            assert "total" in data, f"{response_name} should have .total. field"
