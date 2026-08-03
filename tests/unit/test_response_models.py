"""
Unit tests for API response models

Tests the response model classes including data conversion,
validation, and helper methods for all model types.
"""

from datetime import datetime

import pytest

# Import our new response models
try:
    from resources.lib.api.models.responses import (
        AuthResponse, ProfileData, CMSData, ProfilesResponse,
        ContentItem, SearchResponse, SeasonsResponse, EpisodesResponse, ImageSet,
        StreamResponse, StreamUrl, SubtitleTrack,
        WatchlistResponse, WatchlistItem, PlayheadsResponse, PlayheadData,
        HistoryItem, WatchHistoryResponse
    )
    from resources.lib.api.models.enums import ContentType
except ImportError:
    pytest.skip("New API response models not available", allow_module_level=True)


class TestAuthResponseModels:
    """Test authentication response models"""

    def test_cms_data_creation(self):
        """Test CMSData creation from API data"""
        api_data = {
            "bucket": "crunchyroll",
            "policy": "test_policy",
            "signature": "test_signature",
            "key_pair_id": "test_key_pair"
        }

        cms_data = CMSData.from_dict(api_data)

        assert cms_data.bucket == "crunchyroll"
        assert cms_data.policy == "test_policy"
        assert cms_data.signature == "test_signature"
        assert cms_data.key_pair_id == "test_key_pair"

    def test_profile_data_creation(self):
        """Test ProfileData creation from API data"""
        api_data = {
            "profile_id": "profile123",
            "profile_name": "Test User",
            "avatar": "http://example.com/avatar.jpg",
            "wallpaper": "http://example.com/wallpaper.jpg",
            "is_primary": True
        }

        profile_data = ProfileData.from_dict(api_data)

        assert profile_data.profile_id == "profile123"
        assert profile_data.profile_name == "Test User"
        assert profile_data.is_primary is True

    def test_auth_response_creation(self):
        """Test AuthResponse creation from API data"""
        api_data = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "account_id": "account123",
            "cms": {
                "bucket": "crunchyroll",
                "policy": "test_policy",
                "signature": "test_signature",
                "key_pair_id": "test_key_pair"
            },
            "default_audio_language": "en-US"
        }

        auth_response = AuthResponse.from_dict(api_data)

        assert auth_response.access_token == "test_access_token"
        assert auth_response.refresh_token == "test_refresh_token"
        assert auth_response.token_type == "Bearer"
        assert auth_response.expires_in == 3600
        assert auth_response.account_id == "account123"
        assert isinstance(auth_response.expires_at, datetime)
        assert isinstance(auth_response.cms, CMSData)
        assert auth_response.cms.bucket == "crunchyroll"

    def test_auth_response_expiry_methods(self):
        """Test AuthResponse expiry checking methods"""
        # Create auth response that expires in 1 hour
        api_data = {
            "access_token": "test_token",
            "refresh_token": "refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }

        auth_response = AuthResponse.from_dict(api_data)

        # Should not be expired yet
        assert not auth_response.is_expired()

        # Should expire soon if buffer is large enough
        assert auth_response.expires_soon(buffer_seconds=3700)
        assert not auth_response.expires_soon(buffer_seconds=300)

    def test_profiles_response_creation(self):
        """Test ProfilesResponse creation and helper methods"""
        api_data = {
            "profiles": [
                {
                    "profile_id": "profile1",
                    "profile_name": "Main Profile",
                    "avatar": "avatar1.jpg",
                    "wallpaper": "wallpaper1.jpg",
                    "is_primary": True
                },
                {
                    "profile_id": "profile2",
                    "profile_name": "Kid Profile",
                    "avatar": "avatar2.jpg",
                    "wallpaper": "wallpaper2.jpg",
                    "is_primary": False
                }
            ]
        }

        profiles_response = ProfilesResponse.from_dict(api_data)

        assert len(profiles_response.profiles) == 2
        assert profiles_response.profiles[0].profile_name == "Main Profile"

        # Test helper methods
        primary_profile = profiles_response.get_primary_profile()
        assert primary_profile is not None
        assert primary_profile.profile_id == "profile1"

        profile_by_id = profiles_response.get_profile_by_id("profile2")
        assert profile_by_id is not None
        assert profile_by_id.profile_name == "Kid Profile"


class TestContentResponseModels:
    """Test content response models"""

    def test_image_set_creation(self):
        """Test ImageSet creation from API data"""
        api_data = {
            "images": {
                "thumbnail": [{"source": "http://example.com/thumb.jpg"}],
                "poster_tall": [{"source": "http://example.com/poster_tall.jpg"}],
                "poster_wide": [{"source": "http://example.com/poster_wide.jpg"}]
            }
        }

        image_set = ImageSet.from_dict(api_data)

        assert image_set.thumbnail == "http://example.com/thumb.jpg"
        assert image_set.poster_tall == "http://example.com/poster_tall.jpg"
        assert image_set.poster_wide == "http://example.com/poster_wide.jpg"

        # Test best image selection
        assert image_set.get_best_image("thumbnail") == "http://example.com/thumb.jpg"
        assert image_set.get_best_image("poster_tall") == "http://example.com/poster_tall.jpg"

    def test_content_item_creation(self):
        """Test ContentItem creation from API data"""
        api_data = {
            "id": "episode123",
            "title": "Test Episode",
            "slug": "test-episode",
            "type": "episode",
            "description": "A test episode",
            "series_id": "series123",
            "season_id": "season123",
            "episode_number": 5,
            "season_number": 2,
            "duration_ms": 1440000,  # 24 minutes
            "is_premium_only": True,
            "images": {
                "thumbnail": [{"source": "http://example.com/thumb.jpg"}]
            }
        }

        content_item = ContentItem.from_dict(api_data)

        assert content_item.id == "episode123"
        assert content_item.title == "Test Episode"
        assert content_item.content_type == ContentType.EPISODE
        assert content_item.episode_number == 5
        assert content_item.season_number == 2
        assert content_item.duration_ms == 1440000
        assert content_item.is_premium_only is True
        assert isinstance(content_item.images, ImageSet)

        # Test helper methods
        assert content_item.is_episode()
        assert not content_item.is_series()
        assert not content_item.is_movie()
        assert content_item.get_duration_seconds() == 1440
        assert content_item.get_formatted_duration() == "24:00"

    def test_search_response_creation(self):
        """Test SearchResponse creation and filtering"""
        api_data = {
            "data": [
                {
                    "id": "series1",
                    "title": "Test Series",
                    "slug": "test-series",
                    "type": "series"
                },
                {
                    "id": "episode1",
                    "title": "Test Episode",
                    "slug": "test-episode",
                    "type": "episode"
                },
                {
                    "id": "movie1",
                    "title": "Test Movie",
                    "slug": "test-movie",
                    "type": "movie"
                }
            ],
            "total": 3,
            "has_more": False
        }

        search_response = SearchResponse.from_dict(api_data)

        assert len(search_response.items) == 3
        assert search_response.total == 3
        assert search_response.has_more is False

        # Test filtering methods
        series = search_response.get_series()
        assert len(series) == 1
        assert series[0].title == "Test Series"

        episodes = search_response.get_episodes()
        assert len(episodes) == 1
        assert episodes[0].title == "Test Episode"

        movies = search_response.get_movies()
        assert len(movies) == 1
        assert movies[0].title == "Test Movie"

    def test_seasons_response_creation(self):
        """Test SeasonsResponse creation and helper methods"""
        api_data = {
            "data": [
                {
                    "id": "season1",
                    "title": "Season 1",
                    "type": "season",
                    "season_number": 1
                },
                {
                    "id": "season2",
                    "title": "Season 2",
                    "type": "season",
                    "season_number": 2
                }
            ]
        }

        seasons_response = SeasonsResponse.from_dict(api_data)

        assert len(seasons_response.seasons) == 2

        # Test helper methods
        season_1 = seasons_response.get_season_by_number(1)
        assert season_1 is not None
        assert season_1.title == "Season 1"

        latest_season = seasons_response.get_latest_season()
        assert latest_season is not None
        assert latest_season.season_number == 2

    def test_episodes_response_creation(self):
        """Test EpisodesResponse creation and helper methods"""
        api_data = {
            "data": [
                {
                    "id": "episode1",
                    "title": "Episode 1",
                    "type": "episode",
                    "episode_number": 1,
                    "is_premium_only": False
                },
                {
                    "id": "episode2",
                    "title": "Episode 2",
                    "type": "episode",
                    "episode_number": 2,
                    "is_premium_only": True
                },
                {
                    "id": "episode3",
                    "title": "Episode 3",
                    "type": "episode",
                    "episode_number": 3,
                    "is_premium_only": False
                }
            ]
        }

        episodes_response = EpisodesResponse.from_dict(api_data)

        assert len(episodes_response.episodes) == 3

        # Test helper methods
        episode_2 = episodes_response.get_episode_by_number(2)
        assert episode_2 is not None
        assert episode_2.title == "Episode 2"

        premium_episodes = episodes_response.get_premium_episodes()
        assert len(premium_episodes) == 1
        assert premium_episodes[0].title == "Episode 2"

        free_episodes = episodes_response.get_free_episodes()
        assert len(free_episodes) == 2

        sorted_episodes = episodes_response.sort_by_episode_number()
        assert sorted_episodes[0].episode_number == 1
        assert sorted_episodes[2].episode_number == 3


class TestStreamResponseModels:
    """Test streaming response models"""

    def test_stream_url_creation(self):
        """Test StreamUrl creation and methods"""
        api_data = {
            "url": "http://example.com/stream.m3u8",
            "hardsub_locale": "en-US",
            "adaptive_hls": {"quality": "1080p"}
        }

        stream_url = StreamUrl.from_dict(api_data)

        assert stream_url.url == "http://example.com/stream.m3u8"
        assert stream_url.hardsub_locale == "en-US"
        assert stream_url.is_adaptive()
        assert stream_url.has_hardsubs()

    def test_subtitle_track_creation(self):
        """Test SubtitleTrack creation and methods"""
        api_data = {
            "locale": "en-US",
            "url": "http://example.com/subtitle.ass",
            "format": "ass"
        }

        subtitle_track = SubtitleTrack.from_dict(api_data)

        assert subtitle_track.locale == "en-US"
        assert subtitle_track.url == "http://example.com/subtitle.ass"
        assert subtitle_track.format == "ass"
        assert subtitle_track.is_ass_format()
        assert not subtitle_track.is_srt_format()
        assert subtitle_track.get_language_code() == "en"

    def test_stream_response_creation(self):
        """Test StreamResponse creation and helper methods"""
        api_data = {
            "streams": {
                "adaptive_hls": {
                    "url": "http://example.com/stream.m3u8"
                }
            },
            "subtitles": {
                "en-US": {
                    "url": "http://example.com/en.ass",
                    "format": "ass"
                },
                "ja-JP": {
                    "url": "http://example.com/ja.ass",
                    "format": "ass"
                }
            },
            "token": "stream_token_123"
        }

        stream_response = StreamResponse.from_dict(api_data)

        assert stream_response.has_video_stream()
        assert stream_response.has_subtitles()
        assert stream_response.is_premium_content()
        assert len(stream_response.subtitles) == 2

        # Test subtitle finding methods
        en_subtitle = stream_response.get_subtitle_by_locale("en-US")
        assert en_subtitle is not None
        assert en_subtitle.locale == "en-US"

        en_subtitles = stream_response.get_subtitles_by_language("en")
        assert len(en_subtitles) == 1

        languages = stream_response.get_available_languages()
        assert "en" in languages
        assert "ja" in languages

        locales = stream_response.get_available_locales()
        assert "en-US" in locales
        assert "ja-JP" in locales


class TestUserContentResponseModels:
    """Test user content response models"""

    def test_watchlist_item_creation(self):
        """Test WatchlistItem creation with date parsing"""
        api_data = {
            "id": "episode123",
            "title": "Test Episode",
            "type": "episode",
            "date_added": "2024-01-15T10:30:00Z"
        }

        watchlist_item = WatchlistItem.from_dict(api_data)

        assert isinstance(watchlist_item.content_item, ContentItem)
        assert watchlist_item.content_item.id == "episode123"
        assert isinstance(watchlist_item.date_added, datetime)

    def test_watchlist_response_creation(self):
        """Test WatchlistResponse creation and filtering"""
        api_data = {
            "data": [
                {
                    "id": "series1",
                    "title": "Test Series",
                    "type": "series",
                    "date_added": "2024-01-15T10:30:00Z"
                },
                {
                    "id": "episode1",
                    "title": "Test Episode",
                    "type": "episode",
                    "date_added": "2024-01-16T10:30:00Z"
                }
            ]
        }

        watchlist_response = WatchlistResponse.from_dict(api_data)

        assert len(watchlist_response.items) == 2

        # Test filtering methods
        series_items = watchlist_response.get_series_items()
        assert len(series_items) == 1

        episode_items = watchlist_response.get_episode_items()
        assert len(episode_items) == 1

        # Test finding by content ID
        found_item = watchlist_response.find_by_content_id("episode1")
        assert found_item is not None
        assert found_item.content_item.title == "Test Episode"

    def test_playhead_data_creation(self):
        """Test PlayheadData creation and helper methods"""
        api_data = {
            "content_id": "episode123",
            "playhead": 600,  # 10 minutes
            "fully_watched": False
        }

        playhead_data = PlayheadData.from_dict(api_data)

        assert playhead_data.content_id == "episode123"
        assert playhead_data.playhead == 600
        assert not playhead_data.fully_watched

        # Test helper methods
        progress = playhead_data.get_progress_percentage(1200)  # 20 minutes total
        assert progress == 50.0

        assert playhead_data.is_partially_watched()

    def test_playheads_response_creation(self):
        """Test PlayheadsResponse creation and filtering"""
        api_data = {
            "data": [
                {
                    "content_id": "episode1",
                    "playhead": 0,
                    "fully_watched": False
                },
                {
                    "content_id": "episode2",
                    "playhead": 600,
                    "fully_watched": False
                },
                {
                    "content_id": "episode3",
                    "playhead": 1200,
                    "fully_watched": True
                }
            ]
        }

        playheads_response = PlayheadsResponse.from_dict(api_data)

        assert len(playheads_response.playheads) == 3

        # Test filtering methods
        partially_watched = playheads_response.get_partially_watched()
        assert len(partially_watched) == 1
        assert partially_watched[0].content_id == "episode2"

        fully_watched = playheads_response.get_fully_watched()
        assert len(fully_watched) == 1
        assert fully_watched[0].content_id == "episode3"

        unwatched = playheads_response.get_unwatched()
        assert len(unwatched) == 1
        assert unwatched[0].content_id == "episode1"

        # Test finding by content ID
        found_playhead = playheads_response.get_playhead_by_content_id("episode2")
        assert found_playhead is not None
        assert found_playhead.playhead == 600

    def test_history_item_creation(self):
        """Test HistoryItem creation with timestamp parsing"""
        api_data = {
            "id": "episode123",
            "title": "Test Episode",
            "type": "episode",
            "last_watched": "2024-01-15T15:30:00Z",
            "playhead": 300
        }

        history_item = HistoryItem.from_dict(api_data)

        assert isinstance(history_item.content_item, ContentItem)
        assert history_item.content_item.id == "episode123"
        assert isinstance(history_item.last_watched, datetime)
        assert history_item.playhead == 300

    def test_watch_history_response_creation(self):
        """Test WatchHistoryResponse creation and sorting"""
        api_data = {
            "data": [
                {
                    "id": "episode1",
                    "title": "Episode 1",
                    "type": "episode",
                    "last_watched": "2024-01-15T10:00:00Z"
                },
                {
                    "id": "episode2",
                    "title": "Episode 2",
                    "type": "episode",
                    "last_watched": "2024-01-16T10:00:00Z"
                },
                {
                    "id": "series1",
                    "title": "Series 1",
                    "type": "series",
                    "last_watched": "2024-01-14T10:00:00Z"
                }
            ]
        }

        history_response = WatchHistoryResponse.from_dict(api_data)

        assert len(history_response.items) == 3

        # Test sorting by last watched (most recent first)
        sorted_items = history_response.sort_by_last_watched()
        assert sorted_items[0].content_item.title == "Episode 2"  # Most recent
        assert sorted_items[2].content_item.title == "Series 1"   # Oldest

        # Test getting recent episodes
        recent_episodes = history_response.get_recent_episodes(limit=5)
        assert len(recent_episodes) == 2  # Only episodes, not series
        assert recent_episodes[0].content_item.title == "Episode 2"


class TestModelSerialization:
    """Test model serialization (to_dict methods)"""

    def test_auth_response_serialization(self):
        """Test AuthResponse to_dict conversion"""
        auth_response = AuthResponse(
            access_token="test_token",
            refresh_token="refresh_token",
            token_type="Bearer",
            expires_in=3600,
            account_id="account123"
        )

        result_dict = auth_response.to_dict()

        assert result_dict["access_token"] == "test_token"
        assert result_dict["token_type"] == "Bearer"
        assert result_dict["account_id"] == "account123"

    def test_content_item_serialization(self):
        """Test ContentItem to_dict conversion"""
        content_item = ContentItem(
            id="episode123",
            title="Test Episode",
            slug="test-episode",
            content_type=ContentType.EPISODE,
            episode_number=5
        )

        result_dict = content_item.to_dict()

        assert result_dict["id"] == "episode123"
        assert result_dict["title"] == "Test Episode"
        assert result_dict["episode_number"] == 5

    def test_stream_response_serialization(self):
        """Test StreamResponse to_dict conversion with nested objects"""
        stream_url = StreamUrl(url="http://example.com/stream.m3u8")
        subtitle_track = SubtitleTrack(locale="en-US", url="http://example.com/sub.ass", format="ass")

        stream_response = StreamResponse(
            stream_url=stream_url,
            subtitles=[subtitle_track],
            token="test_token"
        )

        result_dict = stream_response.to_dict()

        assert result_dict["stream_url"]["url"] == "http://example.com/stream.m3u8"
        assert len(result_dict["subtitles"]) == 1
        assert result_dict["subtitles"][0]["locale"] == "en-US"
        assert result_dict["token"] == "test_token"