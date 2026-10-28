"""Tests for PlaybackEndTracker and await_end_result."""

import pytest

from resources.lib.next_episode import playback_end
from resources.lib.next_episode.playback_end import PlaybackEndTracker, await_end_result


class FakeMonitor:
    def __init__(self, abort_after=None, on_wait=None):
        self.abort_after = abort_after
        self.on_wait = on_wait
        self.calls = []

    def waitForAbort(self, seconds):  # noqa: N802 - mirrors xbmc.Monitor
        self.calls.append(seconds)
        index = len(self.calls) - 1
        if self.on_wait is not None:
            self.on_wait(index)
        return self.abort_after is not None and index + 1 >= self.abort_after


class TestPlaybackEndTracker:
    def test_no_event_has_no_result(self):
        tracker = PlaybackEndTracker()

        assert tracker.has_result is False
        assert tracker.ended_regularly is False

    def test_ended_is_regular(self):
        tracker = PlaybackEndTracker()

        tracker.on_ended()

        assert tracker.has_result is True
        assert tracker.ended_regularly is True

    def test_stopped_is_not_regular(self):
        tracker = PlaybackEndTracker()

        tracker.on_stopped()

        assert tracker.has_result is True
        assert tracker.ended_regularly is False

    def test_error_is_not_regular(self):
        tracker = PlaybackEndTracker()

        tracker.on_error()

        assert tracker.has_result is True
        assert tracker.ended_regularly is False

    def test_first_event_wins_stopped_then_ended(self):
        tracker = PlaybackEndTracker()

        tracker.on_stopped()
        tracker.on_ended()

        assert tracker.ended_regularly is False

    def test_first_event_wins_ended_then_stopped(self):
        tracker = PlaybackEndTracker()

        tracker.on_ended()
        tracker.on_stopped()

        assert tracker.ended_regularly is True


class TestAwaitEndResult:
    def test_await_returns_immediately_with_result(self):
        tracker = PlaybackEndTracker()
        tracker.on_ended()
        monitor = FakeMonitor()

        await_end_result(tracker, monitor)

        assert monitor.calls == []

    def test_await_waits_until_timeout_without_result(self):
        tracker = PlaybackEndTracker()
        monitor = FakeMonitor()

        await_end_result(tracker, monitor)

        assert monitor.calls == [0.5, 0.5, 0.5, 0.5]

    def test_await_stops_when_event_arrives(self):
        tracker = PlaybackEndTracker()

        def deliver_on_second_wait(index):
            if index == 1:
                tracker.on_ended()

        monitor = FakeMonitor(on_wait=deliver_on_second_wait)

        await_end_result(tracker, monitor)

        assert len(monitor.calls) == 2
        assert tracker.ended_regularly is True

    def test_await_stops_on_abort(self):
        tracker = PlaybackEndTracker()
        monitor = FakeMonitor(abort_after=1)

        await_end_result(tracker, monitor)

        assert len(monitor.calls) == 1

    def test_await_respects_custom_timeout_and_interval(self):
        tracker = PlaybackEndTracker()
        monitor = FakeMonitor()

        await_end_result(tracker, monitor, timeout=3.0, interval=1.0)

        assert monitor.calls == [1.0, 1.0, 1.0]


class TestPlaybackEndHandler:
    @pytest.fixture
    def builtins(self, monkeypatch):
        calls = []
        monkeypatch.setattr("resources.lib.next_episode.playback_end.xbmc.executebuiltin", calls.append)
        return calls

    def test_ended_marks_regular_end_without_builtin(self, builtins):
        tracker = PlaybackEndTracker()
        handler = playback_end.PlaybackEndHandler(tracker)

        handler.ended()

        assert tracker.ended_regularly is True
        assert builtins == []

    def test_stopped_marks_stop_without_builtin(self, builtins):
        tracker = PlaybackEndTracker()
        handler = playback_end.PlaybackEndHandler(tracker)

        handler.stopped()

        assert tracker.has_result is True
        assert tracker.ended_regularly is False
        assert builtins == []

    def test_error_marks_error_without_builtin(self, builtins):
        tracker = PlaybackEndTracker()
        handler = playback_end.PlaybackEndHandler(tracker)

        handler.error()

        assert tracker.has_result is True
        assert tracker.ended_regularly is False
        assert builtins == []

    def test_stopped_then_ended_keeps_stop(self, builtins):
        tracker = PlaybackEndTracker()
        handler = playback_end.PlaybackEndHandler(tracker)

        handler.stopped()
        handler.ended()

        assert tracker.has_result is True
        assert tracker.ended_regularly is False


class TestPlaybackEndHandlerLogging:
    @pytest.fixture
    def logs(self, monkeypatch):
        records = []
        monkeypatch.setattr(
            playback_end, "crunchy_log", lambda message, level=None: records.append((message, level)), raising=False
        )
        return records

    def test_ended_logs_event(self, logs):
        tracker = PlaybackEndTracker()
        handler = playback_end.PlaybackEndHandler(tracker)

        handler.ended()

        assert logs == [("playback end event: ended", playback_end.xbmc.LOGINFO)]
        assert tracker.ended_regularly is True

    def test_stopped_logs_event(self, logs):
        handler = playback_end.PlaybackEndHandler(PlaybackEndTracker())

        handler.stopped()

        assert logs == [("playback end event: stopped", playback_end.xbmc.LOGINFO)]

    def test_error_logs_event(self, logs):
        handler = playback_end.PlaybackEndHandler(PlaybackEndTracker())

        handler.error()

        assert logs == [("playback end event: error", playback_end.xbmc.LOGINFO)]

    def test_event_after_latched_result_is_logged_as_ignored(self, logs):
        tracker = PlaybackEndTracker()
        handler = playback_end.PlaybackEndHandler(tracker)

        handler.ended()
        handler.stopped()

        assert logs[1] == ("playback end event: stopped (ignored, already latched)", playback_end.xbmc.LOGINFO)
        assert tracker.ended_regularly is True

    def test_one_line_per_event(self, logs):
        handler = playback_end.PlaybackEndHandler(PlaybackEndTracker())

        handler.stopped()
        handler.ended()
        handler.error()

        assert len(logs) == 3
        assert logs[0][0] == "playback end event: stopped"
        assert logs[1][0].endswith(" (ignored, already latched)")
        assert logs[2][0].endswith(" (ignored, already latched)")
