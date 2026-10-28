"""Unit tests for controller.show_profiles: PIN prompt for PIN-protected profiles."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from resources.lib.controller import show_profiles
from resources.lib.models.exceptions import PROFILE_PIN_INVALID, LoginError

PLAIN_PROFILE = {"profile_id": "p1", "profile_name": "Marco", "username": "marco", "avatar": "a.jpg"}
PIN_PROFILE = {
    "profile_id": "p2",
    "profile_name": "Locked",
    "username": "locked",
    "avatar": "b.jpg",
    "is_pin_protected": True,
}


@pytest.fixture
def dialog(ctx):
    """Select the single offered profile; the Dialog mock is shared by select, numeric and notification."""
    ctx.api.profile_data.profile_id = ""
    mock_dialog = MagicMock()
    mock_dialog.select.return_value = 0
    with patch("resources.lib.controller.xbmcgui.Dialog", return_value=mock_dialog):
        yield mock_dialog


def _offer(ctx, profile):
    ctx.api.make_request.return_value = {"profiles": [profile]}


def _notified(dialog, string_id: int) -> bool:
    return any(f"String_{string_id}" in call[0] for call in dialog.notification.call_args_list)


def test_profile_without_pin_flag_switches_without_pin_dialog(ctx, dialog):
    _offer(ctx, PLAIN_PROFILE)

    assert show_profiles(ctx) is True

    dialog.numeric.assert_not_called()
    ctx.api.create_session.assert_called_once()
    assert ctx.api.create_session.call_args[1]["action"] == "refresh_profile"
    assert ctx.api.create_session.call_args[1]["profile_id"] == "p1"
    assert ctx.api.create_session.call_args[1].get("profile_pin") is None


def test_cancelled_pin_dialog_does_not_switch_profile(ctx, dialog):
    _offer(ctx, PIN_PROFILE)
    dialog.numeric.return_value = ""

    assert show_profiles(ctx) is True

    dialog.numeric.assert_called_once()
    ctx.api.create_session.assert_not_called()


def test_correct_pin_switches_profile_with_pin(ctx, dialog):
    _offer(ctx, PIN_PROFILE)
    dialog.numeric.return_value = "1234"

    assert show_profiles(ctx) is True

    assert "String_30314" in dialog.numeric.call_args[0]
    assert dialog.numeric.call_args[1]["bHiddenInput"] is True
    ctx.api.create_session.assert_called_once_with(action="refresh_profile", profile_id="p2", profile_pin="1234")


def test_wrong_pin_notifies_and_asks_again(ctx, dialog):
    _offer(ctx, PIN_PROFILE)
    dialog.numeric.side_effect = ["0000", "1234"]
    ctx.api.create_session.side_effect = [LoginError("Wrong PIN", error_code=PROFILE_PIN_INVALID), None]

    assert show_profiles(ctx) is True

    assert dialog.numeric.call_count == 2
    assert _notified(dialog, 30315)
    assert [c[1]["profile_pin"] for c in ctx.api.create_session.call_args_list] == ["0000", "1234"]


def test_other_login_error_is_propagated(ctx, dialog):
    _offer(ctx, PIN_PROFILE)
    dialog.numeric.return_value = "1234"
    error = LoginError("Server error", error_code="SERVER_ERROR")
    ctx.api.create_session.side_effect = error

    with pytest.raises(LoginError) as exc_info:
        show_profiles(ctx)

    assert exc_info.value is error
    dialog.numeric.assert_called_once()
    assert not _notified(dialog, 30315)
