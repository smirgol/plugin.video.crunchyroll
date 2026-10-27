"""Tests for Countdown, choice mapping, tick loop and countdown setting."""

import threading
from unittest.mock import MagicMock

import pytest

from resources.lib.next_episode.countdown import (
    Countdown,
    NextEpisodeChoice,
    choice_for_action,
    choice_for_click,
    read_countdown_seconds,
    run_countdown_ticks,
)


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


class TestCountdown:
    def test_new_countdown_state(self):
        countdown = Countdown(15)

        assert countdown.remaining == 15
        assert countdown.result is None
        assert countdown.is_finished is False

    @pytest.mark.parametrize("seconds", [0, -1])
    def test_rejects_non_positive_seconds(self, seconds):
        with pytest.raises(ValueError):
            Countdown(seconds)

    def test_ticks_down_to_timeout(self):
        countdown = Countdown(3)

        assert [countdown.tick(), countdown.tick(), countdown.tick()] == [2, 1, 0]
        assert countdown.result is NextEpisodeChoice.TIMEOUT
        assert countdown.is_finished is True

    def test_tick_after_timeout_keeps_zero(self):
        countdown = Countdown(1)
        countdown.tick()

        assert countdown.tick() == 0
        assert countdown.result is NextEpisodeChoice.TIMEOUT

    def test_confirm_sets_continue(self):
        countdown = Countdown(3)

        assert countdown.confirm() is True
        assert countdown.result is NextEpisodeChoice.CONTINUE

    def test_cancel_sets_cancel(self):
        countdown = Countdown(3)

        assert countdown.cancel() is True
        assert countdown.result is NextEpisodeChoice.CANCEL

    def test_tick_after_confirm_changes_nothing(self):
        countdown = Countdown(3)
        countdown.confirm()

        assert countdown.tick() == 3
        assert countdown.result is NextEpisodeChoice.CONTINUE

    def test_cancel_after_confirm_is_ignored(self):
        countdown = Countdown(3)
        countdown.confirm()

        assert countdown.cancel() is False
        assert countdown.result is NextEpisodeChoice.CONTINUE

    def test_confirm_after_timeout_is_ignored(self):
        countdown = Countdown(1)
        countdown.tick()

        assert countdown.confirm() is False
        assert countdown.result is NextEpisodeChoice.TIMEOUT

    def test_confirm_after_cancel_is_ignored(self):
        countdown = Countdown(3)
        countdown.cancel()

        assert countdown.confirm() is False
        assert countdown.result is NextEpisodeChoice.CANCEL

    def test_concurrent_confirm_and_tick_have_single_outcome(self):
        for _ in range(200):
            countdown = Countdown(1)
            confirmed = self._race_confirm_against_tick(countdown)

            assert countdown.result in (NextEpisodeChoice.CONTINUE, NextEpisodeChoice.TIMEOUT)
            if countdown.result is NextEpisodeChoice.CONTINUE:
                assert confirmed == [True]
                assert countdown.remaining == 1
            else:
                assert confirmed == [False]
                assert countdown.remaining == 0

    @staticmethod
    def _race_confirm_against_tick(countdown):
        barrier = threading.Barrier(2)
        confirmed = []

        def run_confirm():
            barrier.wait(timeout=5)
            confirmed.append(countdown.confirm())

        def run_tick():
            barrier.wait(timeout=5)
            countdown.tick()

        threads = [threading.Thread(target=run_confirm), threading.Thread(target=run_tick)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert not any(thread.is_alive() for thread in threads)
        return confirmed


class TestChoiceMapping:
    @pytest.mark.parametrize(
        ("action_id", "expected"),
        [
            (10, NextEpisodeChoice.CANCEL),
            (92, NextEpisodeChoice.CANCEL),
            (13, NextEpisodeChoice.CANCEL),
            (999, None),
            (7, None),
            (1, None),
            (0, None),
        ],
    )
    def test_action_mapping(self, action_id, expected):
        assert choice_for_action(action_id) is expected

    @pytest.mark.parametrize(
        ("control_id", "expected"),
        [
            (1005, NextEpisodeChoice.CONTINUE),
            (1006, NextEpisodeChoice.CANCEL),
            (1000, None),
            (1004, None),
        ],
    )
    def test_click_mapping(self, control_id, expected):
        assert choice_for_click(control_id) is expected


class TestRunCountdownTicks:
    def test_run_ticks_counts_down_and_closes_on_timeout(self):
        countdown = Countdown(3)
        event = FakeStopEvent()
        shown = []
        close = MagicMock()

        run_countdown_ticks(countdown, event, lambda: False, shown.append, close)

        assert shown == [2, 1]
        close.assert_called_once_with()
        assert countdown.result is NextEpisodeChoice.TIMEOUT
        assert event.waits == [1.0, 1.0, 1.0]

    def test_run_ticks_returns_immediately_when_stopped(self):
        countdown = Countdown(3)
        event = FakeStopEvent(is_set=True)
        shown = []
        close = MagicMock()

        run_countdown_ticks(countdown, event, lambda: False, shown.append, close)

        assert shown == []
        close.assert_not_called()
        assert countdown.remaining == 3
        assert countdown.result is None

    def test_run_ticks_abort_cancels_and_closes(self):
        countdown = Countdown(3)
        event = FakeStopEvent()
        shown = []
        close = MagicMock()

        run_countdown_ticks(countdown, event, lambda: True, shown.append, close)

        assert countdown.result is NextEpisodeChoice.CANCEL
        close.assert_called_once_with()
        assert shown == []

    def test_run_ticks_user_choice_does_not_close(self):
        countdown = Countdown(3)

        def on_wait(index):
            if index == 1:
                countdown.confirm()
                event.set()

        event = FakeStopEvent(on_wait=on_wait)
        shown = []
        close = MagicMock()

        run_countdown_ticks(countdown, event, lambda: False, shown.append, close)

        close.assert_not_called()
        assert countdown.result is NextEpisodeChoice.CONTINUE
        assert shown == [2]

    def test_run_ticks_confirm_without_stop_event_does_not_close(self):
        countdown = Countdown(3)

        def on_wait(index):
            if index == 1:
                countdown.confirm()

        event = FakeStopEvent(on_wait=on_wait)
        shown = []
        close = MagicMock()

        run_countdown_ticks(countdown, event, lambda: False, shown.append, close)

        close.assert_not_called()
        assert countdown.result is NextEpisodeChoice.CONTINUE
        assert len(event.waits) == 2

    def test_run_ticks_ignores_runtime_error_from_label(self):
        countdown = Countdown(3)
        event = FakeStopEvent()
        close = MagicMock()
        show_remaining = MagicMock(side_effect=RuntimeError("control gone"))

        run_countdown_ticks(countdown, event, lambda: False, show_remaining, close)

        close.assert_called_once_with()
        assert countdown.result is NextEpisodeChoice.TIMEOUT

    def test_run_ticks_uses_interval(self):
        countdown = Countdown(3)
        event = FakeStopEvent()

        run_countdown_ticks(countdown, event, lambda: False, lambda remaining: None, MagicMock(), interval=0.25)

        assert event.waits == [0.25, 0.25, 0.25]


class TestReadCountdownSeconds:
    @pytest.mark.parametrize(
        ("stored", "expected"),
        [(15, 15), (5, 5), (60, 60), (4, 5), (0, 5), (61, 60), (999, 60), (30, 30)],
    )
    def test_read_countdown_seconds(self, stored, expected):
        addon = MagicMock()
        addon.getSettingInt.return_value = stored

        assert read_countdown_seconds(addon) == expected

    def test_read_countdown_seconds_falls_back_on_exception(self):
        addon = MagicMock()
        addon.getSettingInt.side_effect = RuntimeError("no setting")

        assert read_countdown_seconds(addon) == 15
        addon.getSettingInt.assert_called_once_with("next_episode_countdown")

    @pytest.mark.parametrize("stored", ["20", True])
    def test_read_countdown_seconds_falls_back_on_non_int(self, stored):
        addon = MagicMock()
        addon.getSettingInt.return_value = stored

        assert read_countdown_seconds(addon) == 15
