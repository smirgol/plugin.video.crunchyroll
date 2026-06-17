"""Unit tests for VideoPlayer ctx migration.

TDD: written before implementation.
"""

from unittest.mock import MagicMock, patch

import pytest

from resources.lib.videoplayer import VideoPlayer, update_playhead


@pytest.fixture
def video_player_ctx(ctx):
    """Provide a VideoPlayer constructed with ctx."""
    with patch("resources.lib.videoplayer.xbmc.Player") as mock_player:
        player = VideoPlayer(ctx)
        player._player = mock_player.return_value
        yield player


class TestVideoPlayerInit:
    @patch("resources.lib.videoplayer.xbmc.Player")
    def test_can_be_constructed_with_ctx(self, mock_player, ctx):
        player = VideoPlayer(ctx)
        assert player._ctx is ctx

    @patch("resources.lib.videoplayer.xbmc.Player")
    def test_requires_ctx(self, mock_player):
        with pytest.raises(TypeError):
            VideoPlayer()


class TestVideoPlayerReadsArgsFromCtx:
    def test_get_video_stream_data_passes_ctx_to_videostream(self, video_player_ctx):
        """VideoPlayer should pass its ctx to VideoStream so stream data comes from ctx."""
        ctx = video_player_ctx._ctx
        ctx.args.get_arg.return_value = "some-stream-id"
        ctx.args.addon.getSetting.return_value = "false"

        mock_stream_data = MagicMock()
        mock_stream_data.stream_url = "https://example.com/stream.mpd"
        mock_stream_data.subtitle_urls = None
        mock_stream_data.token = "token123"

        with patch("resources.lib.videoplayer.VideoStream") as mock_videostream_class:
            mock_videostream_class.return_value.get_player_stream_data.return_value = mock_stream_data
            result = video_player_ctx._get_video_stream_data()

        assert result is True
        mock_videostream_class.assert_called_once_with(ctx)


class TestUpdatePlayhead:
    def test_update_playhead_uses_injected_api_and_args(self):
        """update_playhead should call api.make_scraper_request with injected api and args."""
        api = MagicMock()
        api.account_data.account_id = "ACC123"
        api.PLAYHEADS_ENDPOINT = "https://crunchyroll.com/playheads/{0}"
        args = MagicMock()
        args.addon.getSetting.return_value = "true"

        with patch("resources.lib.videoplayer.xbmc"):
            update_playhead("EP123", 42, api, args)

        api.make_scraper_request.assert_called_once()
        called_kwargs = api.make_scraper_request.call_args.kwargs
        assert called_kwargs["method"] == "POST"
        assert called_kwargs["json_data"]["content_id"] == "EP123"
        assert called_kwargs["json_data"]["playhead"] == 42

    def test_update_playhead_respects_sync_setting(self):
        api = MagicMock()
        args = MagicMock()
        args.addon.getSetting.return_value = "false"

        update_playhead("EP123", 42, api, args)
        api.make_scraper_request.assert_not_called()
