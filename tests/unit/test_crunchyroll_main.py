"""Unit tests for login-error handling and the re-auth entry in resources.lib.crunchyroll.main."""

from unittest.mock import MagicMock, patch

import pytest

from resources.lib import crunchyroll
from resources.lib.models.exceptions import CrunchyrollError, LoginError


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Device authentication cancelled by user", "cancelled"),
        ("Refresh token expired", "auth_expired"),
        ("No refresh token available", "auth_expired"),
        ("Network connection failed", "network"),
        ("Server error", "server"),
        ("something odd", "general"),
    ],
)
def test_classify_login_error_login_error(message, expected):
    """classify_login_error keeps the existing message-based classification for LoginError."""
    assert crunchyroll.classify_login_error(LoginError(message)) == expected


def test_classify_login_error_crunchyroll_error():
    """classify_login_error handles CrunchyrollError the same way."""
    assert crunchyroll.classify_login_error(CrunchyrollError("Service unavailable")) == "server"


@pytest.mark.parametrize("error_type", ["cancelled", "network", "server", "general"])
def test_build_login_failed_item_without_mode_for_non_auth_errors(ctx, error_type):
    """Non auth-expired failures render a plain 'Login failed' item without a mode."""
    item = crunchyroll.build_login_failed_item(ctx, error_type)

    assert item["title"] == ctx.args.addon.getLocalizedString(30060)
    assert "mode" not in item


def test_build_login_failed_item_auth_expired_offers_reauth(ctx):
    """An auth_expired failure renders a clickable item that triggers re-authentication."""
    item = crunchyroll.build_login_failed_item(ctx, "auth_expired")

    assert item == {"title": ctx.args.addon.getLocalizedString(30060), "mode": "reauth"}


def _make_args(mode):
    args = MagicMock()
    args.get_arg.side_effect = lambda key, default=None, *_a, **_kw: {"mode": mode}.get(key, default)
    args.addon.getSetting.return_value = ""
    args.addon.getLocalizedString.side_effect = lambda string_id: f"String_{string_id}"
    args.subtitle = "en-US"
    args.subtitle_fallback = ""
    args.argv = ["plugin://plugin.video.crunchyroll/", "1", ""]
    return args


def _run_main(mode, api):
    args = _make_args(mode)
    with patch("resources.lib.crunchyroll.Args") as mock_args_cls, patch(
        "resources.lib.crunchyroll.API", return_value=api
    ), patch("resources.lib.crunchyroll.xbmc"), patch("resources.lib.crunchyroll.xbmcgui"), patch(
        "resources.lib.crunchyroll.xbmcplugin"
    ), patch("resources.lib.crunchyroll.controller"), patch("resources.lib.crunchyroll.view") as mock_view, patch(
        "resources.lib.crunchyroll.show_user_friendly_error"
    ), patch("resources.lib.crunchyroll.check_mode", return_value=True) as mock_check_mode:
        mock_args_cls.from_argv.return_value = args
        result = crunchyroll.main(["plugin://plugin.video.crunchyroll/", "1", ""])
    return result, mock_view, mock_check_mode


def _api():
    api = MagicMock()
    api.profile_data.profile_id = "profile-1"
    return api


def _called_names(mock):
    return [c[0] for c in mock.mock_calls]


def test_main_reauth_destroys_session_before_start():
    """mode=reauth wipes account and profile storage before authentication starts."""
    api = _api()

    _run_main("reauth", api)

    names = _called_names(api)
    assert "destroy" in names
    assert "start" in names
    assert names.index("destroy") < names.index("start")


def test_main_reauth_continues_to_check_mode():
    """mode=reauth does not return early; it proceeds through start() to normal routing."""
    api = _api()

    result, _view, mock_check_mode = _run_main("reauth", api)

    assert result is True
    mock_check_mode.assert_called_once()


@pytest.mark.parametrize("mode", [None, "queue"])
def test_main_without_reauth_does_not_destroy_session(mode):
    """Regular requests keep stored session data."""
    api = _api()

    _run_main(mode, api)

    api.destroy.assert_not_called()
    api.start.assert_called_once()


def test_main_auth_expired_renders_reauth_item():
    """An expired session renders the 'Login failed' item linked to mode=reauth."""
    api = _api()
    api.start.side_effect = LoginError("No refresh token available")

    result, mock_view, _check_mode = _run_main(None, api)

    assert result is False
    mock_view.add_item.assert_called_once()
    assert mock_view.add_item.call_args[0][1] == {"title": "String_30060", "mode": "reauth"}


def test_main_network_failure_renders_plain_failed_item():
    """A non-auth failure keeps the plain 'Login failed' item without a mode."""
    api = _api()
    api.start.side_effect = LoginError("Network connection failed")

    _result, mock_view, _check_mode = _run_main(None, api)

    assert mock_view.add_item.call_args[0][1] == {"title": "String_30060"}
