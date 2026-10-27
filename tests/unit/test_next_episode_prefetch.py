"""Tests for PrefetchTrigger."""

from resources.lib.next_episode.resolver import PrefetchTrigger

CREDITS_WINDOW = {"credits": {"start": 128, "end": 200}}


def test_before_threshold_is_false():
    assert PrefetchTrigger().should_fetch(119.0, 1440.0, {}) is False


def test_at_threshold_is_true():
    assert PrefetchTrigger().should_fetch(120.0, 1440.0, {}) is True


def test_latches_after_first_true():
    trigger = PrefetchTrigger()

    assert trigger.should_fetch(120.0, 1440.0, {}) is True
    assert trigger.should_fetch(500.0, 1440.0, {}) is False


def test_false_does_not_latch():
    trigger = PrefetchTrigger()

    assert trigger.should_fetch(100.0, 1440.0, {}) is False
    assert trigger.should_fetch(130.0, 1440.0, {}) is True


def test_short_runtime_uses_half():
    trigger = PrefetchTrigger()

    assert trigger.should_fetch(99.0, 200.0, {}) is False
    assert trigger.should_fetch(100.0, 200.0, {}) is True


def test_unknown_total_uses_fixed_threshold():
    trigger = PrefetchTrigger()

    assert trigger.should_fetch(119.0, 0.0, {}) is False
    assert trigger.should_fetch(120.0, 0.0, {}) is True


def test_inside_skip_window_is_false():
    assert PrefetchTrigger().should_fetch(130.0, 1440.0, CREDITS_WINDOW) is False


def test_lead_before_skip_window_is_false():
    assert PrefetchTrigger().should_fetch(123.0, 1440.0, CREDITS_WINDOW) is False


def test_just_before_lead_is_true():
    assert PrefetchTrigger().should_fetch(122.0, 1440.0, CREDITS_WINDOW) is True


def test_window_end_is_exclusive():
    assert PrefetchTrigger().should_fetch(200.0, 1440.0, CREDITS_WINDOW) is True


def test_event_without_bounds_is_ignored():
    assert PrefetchTrigger().should_fetch(130.0, 1440.0, {"recap": {}}) is True


def test_passed_window_does_not_block():
    assert PrefetchTrigger().should_fetch(1000.0, 1440.0, {"intro": {"start": 10, "end": 90}}) is True
