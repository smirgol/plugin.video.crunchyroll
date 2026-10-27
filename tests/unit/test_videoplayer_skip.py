"""Unit tests for VideoPlayer skip handling (_instaskip, _ask_to_skip guards)."""

import copy
from unittest.mock import MagicMock, patch

import pytest

from resources.lib.videoplayer import VideoPlayer

SKIP_EVENTS = {"intro": {"start": 10, "end": 100}}


@pytest.fixture
def player(ctx):
    with patch("resources.lib.videoplayer.xbmc.Player") as mock_player_cls:
        vp = VideoPlayer(ctx)
        vp._player = mock_player_cls.return_value
    vp._stream_data = MagicMock()
    vp._stream_data.skip_events_data = copy.deepcopy(SKIP_EVENTS)
    with patch.object(vp, "isPlaying", return_value=True), patch.object(vp, "update_playhead"):
        yield vp


class FakeShowModalDialog:
    """Controllable stand-in for show_modal_dialog: records kwargs, returns ``result``."""

    def __init__(self):
        self.calls = []
        self.result = None

    def __call__(self, dialog_class, xml_filename, **kwargs):
        self.calls.append(kwargs)
        return self.result


@pytest.fixture
def dialog(monkeypatch):
    fake = FakeShowModalDialog()
    monkeypatch.setattr("resources.lib.videoplayer.show_modal_dialog", fake)
    return fake


class TestInstaskip:
    def test_instaskip_seeks_to_section_end_and_syncs(self, player):
        """Characterization: existing behaviour for a valid section."""
        player._instaskip("intro")

        player._player.seekTime.assert_called_once_with(100)
        player.update_playhead.assert_called_once()

    def test_instaskip_unknown_section_does_nothing(self, player):
        player._instaskip("credits")

        player._player.seekTime.assert_not_called()
        player.update_playhead.assert_not_called()

    def test_instaskip_section_without_end_does_not_seek_to_zero(self, player):
        player._stream_data.skip_events_data = {"intro": {"start": 10}}

        player._instaskip("intro")

        player._player.seekTime.assert_not_called()
        player.update_playhead.assert_not_called()

    def test_instaskip_when_not_playing_does_nothing(self, player):
        player.isPlaying.return_value = False

        player._instaskip("intro")

        player._player.seekTime.assert_not_called()
        player.update_playhead.assert_not_called()


class TestAskToSkipGuards:
    def test_ask_to_skip_unknown_section_shows_no_dialog(self, player, dialog):
        player._ask_to_skip("credits")

        assert dialog.calls == []

    def test_ask_to_skip_dialog_duration_is_capped(self, player, dialog):
        """Characterization: dialog duration is capped by the modal maximum."""
        player._ask_to_skip("intro")

        assert len(dialog.calls) == 1
        assert dialog.calls[0]["seconds"] == 10

    def test_ask_to_skip_dialog_duration_for_short_section(self, player, dialog):
        """Characterization: short sections use their own length."""
        player._stream_data.skip_events_data = {"intro": {"start": 10, "end": 15}}

        player._ask_to_skip("intro")

        assert dialog.calls[0]["seconds"] == 5
