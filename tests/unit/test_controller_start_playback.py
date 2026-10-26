"""Unit tests for controller.start_playback: the stream is always released, original exceptions propagate."""

from unittest.mock import MagicMock

import pytest

import resources.lib.controller as controller


@pytest.fixture
def video_player(ctx, monkeypatch):
    player = MagicMock()
    monkeypatch.setattr(controller, "VideoPlayer", MagicMock(return_value=player))
    ctx.monitor.abortRequested.return_value = False
    monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: "false")
    return player


def test_finished_called_after_regular_loop_end(ctx, video_player):
    video_player.isStartingOrPlaying.side_effect = [True, False]

    controller.start_playback(ctx)

    video_player.finished.assert_called_once()
    video_player.check_skipping.assert_called_once()


def test_finished_called_when_loop_raises(ctx, video_player):
    video_player.isStartingOrPlaying.return_value = True
    video_player.check_skipping.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        controller.start_playback(ctx)

    video_player.finished.assert_called_once()


def test_finished_called_when_start_raises(ctx, video_player):
    video_player.start_playback.side_effect = RuntimeError("start")

    with pytest.raises(RuntimeError, match="start"):
        controller.start_playback(ctx)

    video_player.finished.assert_called_once()
    video_player.check_skipping.assert_not_called()
