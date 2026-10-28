"""Tests for ChoiceLatch and the Countdown decision/total."""

import itertools
import threading

import pytest

from resources.lib.next_episode.countdown import ChoiceLatch, Countdown, NextEpisodeChoice

DECISIONS = [
    ("confirm", NextEpisodeChoice.CONTINUE),
    ("cancel", NextEpisodeChoice.CANCEL),
    ("time_out", NextEpisodeChoice.TIMEOUT),
]


def race(first, second):
    barrier = threading.Barrier(2)
    outcomes = [None, None]

    def run(index, decide):
        barrier.wait(timeout=5)
        outcomes[index] = decide()

    threads = [threading.Thread(target=run, args=(i, d)) for i, d in enumerate((first, second))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    return outcomes


class TestChoiceLatch:
    def test_new_latch_is_open(self):
        latch = ChoiceLatch()

        assert latch.result is None
        assert latch.is_finished is False

    @pytest.mark.parametrize(("method", "expected"), DECISIONS)
    def test_each_decision_wins_on_open_latch(self, method, expected):
        latch = ChoiceLatch()

        assert getattr(latch, method)() is True
        assert latch.result is expected
        assert latch.is_finished is True

    @pytest.mark.parametrize(
        ("first", "second"),
        list(itertools.product(("confirm", "cancel", "time_out"), repeat=2)),
    )
    def test_first_decision_wins(self, first, second):
        latch = ChoiceLatch()
        getattr(latch, first)()
        expected = latch.result

        assert getattr(latch, second)() is False
        assert latch.result is expected

    def test_concurrent_decisions_have_single_winner(self):
        for _ in range(200):
            latch = ChoiceLatch()
            outcomes = race(latch.confirm, latch.cancel)

            assert sorted(outcomes) == [False, True]
            winner = NextEpisodeChoice.CONTINUE if outcomes[0] else NextEpisodeChoice.CANCEL
            assert latch.result is winner


class TestCountdownDecision:
    def test_total_is_initial_seconds(self):
        c = Countdown(5)
        assert c.total == 5

        c.tick()
        c.tick()

        assert c.total == 5
        assert c.remaining == 3

    def test_decision_is_owned_latch(self):
        c = Countdown(5)

        assert isinstance(c.decision, ChoiceLatch)
        assert c.decision is c.decision

    def test_decision_confirm_is_countdown_result(self):
        c = Countdown(5)

        c.decision.confirm()

        assert c.result is NextEpisodeChoice.CONTINUE
        assert c.is_finished is True

    def test_countdown_cancel_finishes_decision(self):
        c = Countdown(5)

        c.cancel()

        assert c.decision.result is NextEpisodeChoice.CANCEL

    def test_timeout_finishes_decision(self):
        c = Countdown(1)

        assert c.tick() == 0
        assert c.decision.result is NextEpisodeChoice.TIMEOUT

    def test_tick_on_last_second_after_cancel_keeps_remaining(self):
        """Characterization: already true for the pre-refactor Countdown."""
        c = Countdown(1)
        c.cancel()

        assert c.tick() == 1
        assert c.remaining == 1
        assert c.result is NextEpisodeChoice.CANCEL

    def test_tick_on_last_second_after_decision_confirm_keeps_remaining(self):
        """Characterization of the is_finished guard before the decrement reaches zero."""
        c = Countdown(1)
        c.decision.confirm()

        assert c.tick() == 1
        assert c.remaining == 1
        assert c.result is NextEpisodeChoice.CONTINUE

    def test_tick_that_loses_the_timeout_race_keeps_remaining(self, monkeypatch):
        c = Countdown(1)
        latch = c.decision

        def decided_meanwhile():
            latch.cancel()  # another thread wins between the guard and time_out
            return ChoiceLatch.time_out(latch)  # False, the latch is already decided

        monkeypatch.setattr(latch, "time_out", decided_meanwhile)

        assert c.tick() == 1
        assert c.remaining == 1
        assert c.result is NextEpisodeChoice.CANCEL
