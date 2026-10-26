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


class TestClearAllActiveStreams:
    TOKENS = ["tok-secret-1", "tok-secret-2"]

    def _run(self, player, tokens):
        with patch.object(player, "get_active_streams", return_value=list(tokens)), patch.object(
            player, "clear_active_stream"
        ) as mock_clear, patch("resources.lib.videoplayer.crunchy_log") as mock_log:
            player.clear_all_active_streams()
        return mock_clear, mock_log

    def test_clears_each_active_stream_in_order(self, video_player_ctx):
        mock_clear, _ = self._run(video_player_ctx, self.TOKENS)

        assert [c.args for c in mock_clear.call_args_list] == [(token,) for token in self.TOKENS]

    def test_logs_one_line_per_cleared_stream_without_token(self, video_player_ctx):
        _, mock_log = self._run(video_player_ctx, self.TOKENS)

        logged = [" ".join(str(a) for a in (*c.args, *c.kwargs.values())) for c in mock_log.call_args_list]
        for token in self.TOKENS:
            leaking = [line for line in logged if token in line]
            assert not leaking, f"stream token leaked into log: {leaking}"
        assert mock_log.call_count == len(self.TOKENS)

    def test_no_active_streams_neither_clears_nor_logs(self, video_player_ctx):
        mock_clear, mock_log = self._run(video_player_ctx, [])

        mock_clear.assert_not_called()
        mock_log.assert_not_called()


class TestClearActiveStreamWithoutStreamData:
    @pytest.fixture(autouse=True)
    def _episode_and_endpoint(self, video_player_ctx, monkeypatch):
        ctx = video_player_ctx._ctx
        monkeypatch.setattr(ctx.api, "STREAMS_ENDPOINT_CLEAR_STREAM", "https://play/{}/{}")
        monkeypatch.setattr(ctx.args, "get_arg", lambda name, *a, **k: "EP1" if name == "episode_id" else None)

    def test_finished_without_stream_data_does_not_raise(self, video_player_ctx):
        video_player_ctx._stream_data = None

        video_player_ctx.finished()

        video_player_ctx._ctx.api.make_request.assert_not_called()
        assert video_player_ctx.clearedStream is True

    def test_clear_all_active_streams_uses_passed_token_without_stream_data(self, video_player_ctx, monkeypatch):
        video_player_ctx._stream_data = None
        monkeypatch.setattr(video_player_ctx, "get_active_streams", lambda: ["tok1"])

        video_player_ctx.clear_all_active_streams()

        video_player_ctx._ctx.api.make_request.assert_called_once_with(method="DELETE", url="https://play/EP1/tok1")

    def test_clear_active_stream_uses_stream_token_by_default(self, video_player_ctx):
        video_player_ctx._stream_data = MagicMock(token="tok9")

        video_player_ctx.clear_active_stream()

        video_player_ctx._ctx.api.make_request.assert_called_once_with(method="DELETE", url="https://play/EP1/tok9")

    def test_clear_active_stream_without_episode_id_makes_no_request(self, video_player_ctx, monkeypatch):
        monkeypatch.setattr(video_player_ctx._ctx.args, "get_arg", lambda name, *a, **k: None)
        video_player_ctx._stream_data = None

        video_player_ctx.clear_active_stream("tok1")

        video_player_ctx._ctx.api.make_request.assert_not_called()


class TestReadApi:
    def test_playable_item_none_without_stream_data(self, video_player_ctx):
        video_player_ctx._stream_data = None

        assert video_player_ctx.playable_item is None

    def test_playable_item_from_stream_data(self, video_player_ctx):
        sentinel = object()
        video_player_ctx._stream_data = MagicMock(playable_item=sentinel)

        assert video_player_ctx.playable_item is sentinel

    def test_skip_events_empty_without_stream_data(self, video_player_ctx):
        video_player_ctx._stream_data = None

        assert video_player_ctx.skip_events == {}

    def test_skip_events_is_copy(self, video_player_ctx):
        video_player_ctx._stream_data = MagicMock()
        video_player_ctx._stream_data.skip_events_data = {"intro": {"start": 10, "end": 90}}

        result = video_player_ctx.skip_events
        assert result == {"intro": {"start": 10, "end": 90}}

        result.pop("intro")
        assert video_player_ctx._stream_data.skip_events_data == {"intro": {"start": 10, "end": 90}}

    def test_playback_times_when_playing(self, video_player_ctx, monkeypatch):
        monkeypatch.setattr(video_player_ctx, "isPlaying", lambda: True)
        video_player_ctx._player.getTime.return_value = 200.0
        video_player_ctx._player.getTotalTime.return_value = 1440.0

        assert video_player_ctx.playback_times() == (200.0, 1440.0)

    def test_playback_times_none_when_not_playing(self, video_player_ctx, monkeypatch):
        monkeypatch.setattr(video_player_ctx, "isPlaying", lambda: False)

        assert video_player_ctx.playback_times() is None
        video_player_ctx._player.getTime.assert_not_called()

    def test_playback_times_none_when_player_raises(self, video_player_ctx, monkeypatch):
        monkeypatch.setattr(video_player_ctx, "isPlaying", lambda: True)
        video_player_ctx._player.getTime.side_effect = RuntimeError

        assert video_player_ctx.playback_times() is None
