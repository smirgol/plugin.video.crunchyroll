"""Tests for run_abort_watch."""

from unittest.mock import MagicMock

from resources.lib.next_episode.countdown import ChoiceLatch, NextEpisodeChoice, run_abort_watch


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


class TestRunAbortWatch:
    def test_abort_cancels_and_closes(self):
        latch = ChoiceLatch()
        event = FakeStopEvent()
        close = MagicMock()
        abort = MagicMock(return_value=True)

        run_abort_watch(latch, event, abort, close)

        assert latch.result is NextEpisodeChoice.CANCEL
        close.assert_called_once_with()
        assert event.waits == [1.0]

    def test_returns_immediately_when_stopped(self):
        latch = ChoiceLatch()
        event = FakeStopEvent(is_set=True)
        close = MagicMock()
        abort = MagicMock(return_value=True)

        run_abort_watch(latch, event, abort, close)

        close.assert_not_called()
        abort.assert_not_called()
        assert latch.result is None
        assert event.waits == [1.0]

    def test_waits_without_abort_until_stopped(self):
        latch = ChoiceLatch()
        event = FakeStopEvent(on_wait=lambda index: event.set() if index == 2 else None)
        close = MagicMock()
        abort = MagicMock(return_value=False)

        run_abort_watch(latch, event, abort, close)

        close.assert_not_called()
        assert len(event.waits) == 3
        assert latch.result is None
        assert abort.call_count == 2

    def test_abort_after_user_decision_does_not_close(self):
        latch = ChoiceLatch()
        latch.confirm()
        event = FakeStopEvent()
        close = MagicMock()
        abort = MagicMock(return_value=True)

        run_abort_watch(latch, event, abort, close)

        close.assert_not_called()
        assert latch.result is NextEpisodeChoice.CONTINUE
        assert event.waits == [1.0]

    def test_uses_interval(self):
        latch = ChoiceLatch()
        event = FakeStopEvent()
        abort = MagicMock(return_value=True)

        run_abort_watch(latch, event, abort, MagicMock(), interval=0.25)

        assert event.waits == [0.25]
