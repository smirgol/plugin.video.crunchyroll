"""Tests for the skip dialog playback-end watcher and show_modal_dialog lifecycle."""

import threading
from unittest.mock import MagicMock

import pytest

from resources.lib.gui import run_close_when_playback_ends, show_modal_dialog

SKIP_XML = "plugin-video-crunchyroll-skip.xml"


class FakeStopEvent:
    def __init__(self, on_wait=None, is_set=False):
        self._set = is_set
        self.on_wait = on_wait
        self.waits = []

    def set(self):
        self._set = True

    def is_set(self):
        return self._set

    def wait(self, timeout):
        self.waits.append(timeout)
        index = len(self.waits) - 1
        if self.on_wait is not None:
            self.on_wait(index)
        return self.is_set()


class TestRunCloseWhenPlaybackEnds:
    def test_closes_when_playback_ends(self):
        event = FakeStopEvent()
        close = MagicMock()

        run_close_when_playback_ends(
            event, MagicMock(side_effect=[True, True, False]), MagicMock(return_value=False), close
        )

        close.assert_called_once_with()
        assert event.waits == [0.5, 0.5, 0.5]

    def test_keeps_dialog_while_playing_until_stopped(self):
        event = FakeStopEvent(on_wait=lambda index: event.set() if index == 2 else None)
        close = MagicMock()

        run_close_when_playback_ends(event, MagicMock(return_value=True), MagicMock(return_value=False), close)

        close.assert_not_called()
        assert len(event.waits) == 3

    def test_returns_immediately_when_already_stopped(self):
        event = FakeStopEvent(is_set=True)
        close = MagicMock()
        is_playing = MagicMock()

        run_close_when_playback_ends(event, is_playing, MagicMock(return_value=False), close)

        close.assert_not_called()
        is_playing.assert_not_called()
        assert event.waits == [0.5]

    def test_closes_on_abort_without_asking_player(self):
        event = FakeStopEvent()
        close = MagicMock()
        is_playing = MagicMock()

        run_close_when_playback_ends(event, is_playing, MagicMock(return_value=True), close)

        close.assert_called_once_with()
        is_playing.assert_not_called()

    def test_runtime_error_from_player_counts_as_ended(self):
        event = FakeStopEvent()
        close = MagicMock()

        run_close_when_playback_ends(event, MagicMock(side_effect=RuntimeError), MagicMock(return_value=False), close)

        close.assert_called_once_with()

    def test_does_not_close_when_stopped_meanwhile(self):
        event = FakeStopEvent()
        close = MagicMock()

        def user_closed_dialog():
            event.set()
            return False

        run_close_when_playback_ends(event, user_closed_dialog, MagicMock(return_value=False), close)

        close.assert_not_called()

    def test_uses_custom_interval(self):
        event = FakeStopEvent()

        run_close_when_playback_ends(
            event, MagicMock(return_value=False), MagicMock(return_value=False), MagicMock(), interval=0.1
        )

        assert event.waits == [0.1]


@pytest.fixture
def events(monkeypatch):
    recorded = []
    monkeypatch.setattr("resources.lib.gui.xbmc.executebuiltin", recorded.append)
    return recorded


@pytest.fixture
def fake_dialog(events, monkeypatch):
    class FakeDialog:
        instances = []
        on_modal = None

        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs
            self.watch_thread = MagicMock()
            FakeDialog.instances.append(self)

        def doModal(self):  # noqa: N802 - mirrors xbmcgui.WindowXMLDialog
            events.append("doModal")
            if FakeDialog.on_modal is not None:
                FakeDialog.on_modal(self)

    return FakeDialog


def show(dialog_class, stop_event):
    show_modal_dialog(dialog_class, SKIP_XML, seconds=10, addon_path="/addon", stop_event=stop_event)


class TestShowModalDialog:
    def test_alarm_is_set_before_modal(self, fake_dialog, events):
        """Characterization: existing behaviour, may be green before the change."""
        show(fake_dialog, threading.Event())

        assert events == ["AlarmClock(closedialog,Action(noop),00:10,silent)", "doModal"]

    def test_stops_watch_and_joins_after_modal(self, fake_dialog):
        stop_event = threading.Event()
        fake_dialog.on_modal = lambda d: self._assert_not_set(d)

        show(fake_dialog, stop_event)

        assert stop_event.is_set()
        fake_dialog.instances[0].watch_thread.join.assert_called_once_with(timeout=2.0)

    @staticmethod
    def _assert_not_set(dialog):
        assert not dialog.kwargs["stop_event"].is_set()

    def test_stops_watch_when_modal_raises(self, fake_dialog):
        stop_event = threading.Event()

        def fail(_dialog):
            raise RuntimeError("modal failed")

        fake_dialog.on_modal = fail

        with pytest.raises(RuntimeError):
            show(fake_dialog, stop_event)

        assert stop_event.is_set()
        fake_dialog.instances[0].watch_thread.join.assert_called_once_with(timeout=2.0)

    def test_skips_join_without_watch_thread(self, fake_dialog):
        stop_event = threading.Event()

        def drop_thread(dialog):
            dialog.watch_thread = None

        fake_dialog.on_modal = drop_thread

        show(fake_dialog, stop_event)

        assert stop_event.is_set()

    def test_passes_kwargs_to_dialog(self, fake_dialog):
        """Characterization: existing argument passing, may be green before the change."""
        stop_event = threading.Event()

        show(fake_dialog, stop_event)

        dialog = fake_dialog.instances[0]
        assert dialog.args == (SKIP_XML, "/addon", "default", "1080i")
        assert dialog.kwargs["stop_event"] is stop_event
