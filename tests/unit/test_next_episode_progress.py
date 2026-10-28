"""Tests for remaining_percent."""

import pytest

from resources.lib.next_episode.countdown import Countdown, remaining_percent


@pytest.mark.parametrize(
    ("remaining", "total", "expected"),
    [
        (15, 15, 100.0),
        (0, 15, 0.0),
        (5, 10, 50.0),
        (1, 5, 20.0),
        (1, 3, pytest.approx(100 / 3)),
    ],
)
def test_percent_values(remaining, total, expected):
    assert remaining_percent(remaining, total) == expected


@pytest.mark.parametrize(
    ("remaining", "total", "expected"),
    [
        (20, 10, 100.0),
        (-1, 10, 0.0),
    ],
)
def test_percent_is_clamped(remaining, total, expected):
    assert remaining_percent(remaining, total) == expected


def test_percent_returns_float():
    assert isinstance(remaining_percent(3, 3), float)


def test_percent_runs_down_with_countdown():
    countdown = Countdown(4)
    values = [remaining_percent(countdown.remaining, countdown.total)]

    while not countdown.is_finished:
        countdown.tick()
        values.append(remaining_percent(countdown.remaining, countdown.total))

    assert values == [100.0, 75.0, 50.0, 25.0, 0.0]
