"""Unit tests for VideoStream ctx migration.

TDD: written before implementation.
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def video_stream_ctx():
    """Provide a context that lets VideoStream exercise the ctx path."""
    from resources.lib.context import PluginContext

    mock_api = MagicMock()
    mock_api.STREAMS_ENDPOINT_DRM_ANDROID_TV = "https://www.crunchyroll.com/content/v2/cms/videos/{}/streams"
    mock_api.SKIP_EVENTS_ENDPOINT = "https://www.crunchyroll.com/skip-events/{}"
    mock_api.INTRO_V2_ENDPOINT = "https://www.crunchyroll.com/intro/{}"

    mock_account = MagicMock()
    mock_api.account_data = mock_account

    mock_args = MagicMock()
    mock_args.get_arg = MagicMock(return_value="episode-123")
    mock_args.addon = MagicMock()
    mock_args.addon.getSetting = MagicMock(return_value="true")
    mock_args.subtitle = "de-DE"
    mock_args.subtitle_fallback = "en-US"
    mock_args.addon_name = "Test"
    mock_args.argv = ["", "1", "?mode=videoplay", "resume:false"]

    mock_monitor = MagicMock()

    return PluginContext(api=mock_api, args=mock_args, monitor=mock_monitor)


class TestVideoStreamInit:
    def test_can_be_constructed_with_ctx(self, video_stream_ctx):
        from resources.lib.videostream import VideoStream

        stream = VideoStream(video_stream_ctx)
        assert stream._ctx is video_stream_ctx

    def test_requires_ctx(self):
        from resources.lib.videostream import VideoStream

        with pytest.raises(TypeError):
            VideoStream()


class TestVideoStreamReadsArgsFromCtx:
    @patch("resources.lib.videostream.asyncio")
    def test_get_player_stream_data_uses_ctx_args_stream_id(self, mock_asyncio, video_stream_ctx):
        from resources.lib.videostream import VideoStream

        # minimal async result so the method can finish
        mock_asyncio.run.return_value = {
            "stream_data": {
                "url": "https://example.com/stream.mpd",
                "subtitles": [],
                "playheads": [],
                "token": "token123",
            }
        }

        stream = VideoStream(video_stream_ctx)
        stream.get_player_stream_data()

        video_stream_ctx.args.get_arg.assert_called_with("stream_id")
