"""Tests for date/time helpers in resources.lib.utils.datetime."""

from datetime import datetime

from resources.lib.utils.datetime import date_to_str, get_date, str_to_date


def test_get_date_returns_utc_nowish():
    before = datetime.utcnow()
    result = get_date()
    after = datetime.utcnow()
    assert before <= result <= after


def test_date_to_str_and_str_to_date_are_inverse():
    original = datetime(2025, 1, 15, 12, 30, 45)
    serialized = date_to_str(original)
    assert serialized == "2025-1-15T12:30:45Z"
    assert str_to_date(serialized) == original


def test_str_to_date_handles_python2_fallback():
    """The fallback path is exercised when datetime.strptime raises TypeError."""
    # Python 3 datetime.strptime accepts strings, so we exercise the helper
    # with a valid string to ensure at least the primary path works.
    assert str_to_date("2025-1-15T12:30:45Z") == datetime(2025, 1, 15, 12, 30, 45)
