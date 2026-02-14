"""Mock API responses for unit tests"""

AUTH_TOKEN_RESPONSE = {
    "access_token": "mock_access_token_abcdef123456",
    "refresh_token": "mock_refresh_token_xyz789",
    "expires_in": 300,
    "token_type": "Bearer",
    "scope": "offline_access",
    "country": "US",
    "account_id": "mock_account_12345",
    "profile_id": "mock_profile_67890"
}

DEVICE_CODE_RESPONSE = {
    "device_code": "mock_device_code_123abc",
    "user_code": "ABCD1234",
    "verification_url": "https://www.crunchyroll.com/activate",
    "expires_in": 300,
    "interval": 5
}

PROFILE_RESPONSE = {
    "avatar": "default_avatar_001.png",
    "email": "test@example.com",
    "maturity_rating": "M3",
    "preferred_communication_language": "en-US",
    "preferred_content_audio_language": "en-US",
    "preferred_content_subtitle_language": "en-US",
    "username": "TestUser",
    "account_id": "mock_account_12345",
    "profile_id": "mock_profile_67890",
    "profile_name": "Main Profile"
}

BROWSE_RESPONSE = {
    "total": 50,
    "data": [
        {
            "id": "GRVN8VK8R",
            "title": "Test Anime Series",
            "type": "series",
            "slug": "test-anime-series",
            "description": "A test anime series for testing",
            "images": {
                "poster_tall": [[{
                    "source": "https://www.crunchyroll.com/imgsrv/test-poster.jpg",
                    "type": "poster_tall",
                    "width": 240,
                    "height": 360
                }]],
                "poster_wide": [[{
                    "source": "https://www.crunchyroll.com/imgsrv/test-banner.jpg",
                    "type": "poster_wide",
                    "width": 1920,
                    "height": 1080
                }]]
            },
            "episode_count": 24,
            "season_count": 2
        }
    ]
}

SEASONS_RESPONSE = {
    "total": 2,
    "data": [
        {
            "id": "GRJ0X123Y",
            "channel_id": "crunchyroll",
            "title": "Season 1",
            "slug": "test-anime-season-1",
            "series_id": "GRVN8VK8R",
            "season_number": 1,
            "is_subbed": True,
            "is_dubbed": True,
            "audio_locales": ["ja-JP", "en-US"],
            "subtitle_locales": ["en-US", "de-DE", "es-ES"]
        },
        {
            "id": "GRJ0X456Z",
            "channel_id": "crunchyroll",
            "title": "Season 2",
            "slug": "test-anime-season-2",
            "series_id": "GRVN8VK8R",
            "season_number": 2,
            "is_subbed": True,
            "is_dubbed": False,
            "audio_locales": ["ja-JP"],
            "subtitle_locales": ["en-US", "de-DE"]
        }
    ]
}

EPISODES_RESPONSE = {
    "total": 12,
    "data": [
        {
            "id": "GRVN1234X",
            "channel_id": "crunchyroll",
            "title": "Episode 1: The Beginning",
            "slug": "episode-1-the-beginning",
            "series_id": "GRVN8VK8R",
            "series_title": "Test Anime Series",
            "season_id": "GRJ0X123Y",
            "season_title": "Season 1",
            "season_number": 1,
            "episode": "1",
            "episode_number": 1,
            "sequence_number": 1,
            "description": "The first episode",
            "duration_ms": 1420000,
            "is_subbed": True,
            "is_dubbed": True,
            "is_premium_only": True,
            "images": {
                "thumbnail": [[{
                    "source": "https://www.crunchyroll.com/imgsrv/episode-thumb.jpg",
                    "type": "thumbnail",
                    "width": 640,
                    "height": 360
                }]]
            }
        }
    ]
}

STREAM_RESPONSE = {
    "audio_locale": "ja-JP",
    "subtitles": {
        "en-US": {
            "locale": "en-US",
            "url": "https://v.vrv.co/evs3/subs/en-US.ass",
            "format": "ass"
        },
        "de-DE": {
            "locale": "de-DE",
            "url": "https://v.vrv.co/evs3/subs/de-DE.ass",
            "format": "ass"
        }
    },
    "streams": {
        "adaptive_hls": {
            "": {
                "hardsub_locale": "",
                "url": "https://v.vrv.co/evs3/stream.m3u8"
            }
        }
    },
    "token": "mock_stream_token_abc123",
    "url": "/cms/v2/videos/GRVN1234X/streams"
}

SEARCH_RESPONSE = {
    "total": 5,
    "data": [
        {
            "id": "GRVN8VK8R",
            "title": "Test Search Result",
            "type": "series",
            "slug": "test-search-result",
            "description": "A search result",
            "images": {
                "poster_tall": [[{
                    "source": "https://www.crunchyroll.com/imgsrv/search-result.jpg"
                }]]
            }
        }
    ]
}

WATCHLIST_RESPONSE = {
    "total": 3,
    "data": [
        {
            "id": "GRVN8VK8R",
            "title": "Watchlist Item",
            "type": "series",
            "is_favorite": True,
            "new": False,
            "new_content": False,
            "playhead": 0
        }
    ]
}

ERROR_RESPONSE_401 = {
    "error": "invalid_grant",
    "message": "Invalid refresh token",
    "code": "invalid_credentials"
}

ERROR_RESPONSE_429 = {
    "error": "rate_limit_exceeded",
    "message": "Too many requests",
    "code": "too_many_requests"
}

ERROR_RESPONSE_500 = {
    "error": "internal_server_error",
    "message": "Internal server error",
    "code": "server_error"
}
