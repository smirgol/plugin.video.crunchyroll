"""Focused unit tests for resources.lib.auth.AuthManager.

These tests exercise AuthManager directly using a lightweight fake API that
provides the same attributes/methods the real API exposes to AuthManager.
This avoids the circular pass-through that existed before Phase 9b.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from resources.lib.auth import AUTHORIZATION, AuthManager
from resources.lib.models.account import AccountData, ProfileData
from resources.lib.models.exceptions import LoginError


class FakeAPI:
    """Minimal API stand-in for AuthManager tests."""

    CRUNCHYROLL_UA = "test-ua"

    def __init__(self):
        self.account_data = AccountData({})
        self.profile_data = ProfileData({})
        self.api_headers = {}
        self.refresh_attempts = 0
        self.args: Any = None

    def make_unauthenticated_request(self, method, url, headers=None, **kwargs):
        return kwargs.get("json_data") or kwargs.get("data") or {}


def make_manager(**overrides):
    api = FakeAPI()
    api.args = MagicMock()
    api.args.device_id = "test-device-id"
    api.args.addon_name = "TestCrunchyroll"
    api.args.addon.getLocalizedString.return_value = "localized"
    for key, value in overrides.items():
        setattr(api, key, value)
    return AuthManager(api_instance=api), api


def test_auth_manager_stores_api_reference():
    """AuthManager holds the API instance it was given."""
    api = FakeAPI()
    manager = AuthManager(api_instance=api)
    assert manager.api is api


def test_create_auth_scraper_returns_scraper():
    """create_auth_scraper builds a CloudScraper configured with the API UA."""
    manager, api = make_manager()
    with patch("resources.lib.auth.cloudscraper.create_scraper") as mock_create:
        mock_create.return_value = MagicMock()
        scraper = manager.create_auth_scraper()
        assert scraper is mock_create.return_value
        mock_create.assert_called_once_with(delay=10, browser={"custom": api.CRUNCHYROLL_UA})


def test_create_auth_scraper_returns_none_on_failure():
    """create_auth_scraper swallows initialization errors and returns None."""
    manager, _api = make_manager()
    with patch("resources.lib.auth.cloudscraper.create_scraper", side_effect=RuntimeError("boom")):
        assert manager.create_auth_scraper() is None


def test_is_token_valid_when_recent():
    """is_token_valid returns True for a token issued in the future."""
    from datetime import datetime, timedelta

    manager, api = make_manager()
    api.account_data = AccountData(
        {
            "access_token": "tok",
            "expires": (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    assert manager.is_token_valid() is True


def test_is_token_valid_when_expired():
    """is_token_valid returns False for a token in the past."""
    from datetime import datetime, timedelta

    manager, api = make_manager()
    api.account_data = AccountData(
        {
            "access_token": "tok",
            "expires": (datetime.utcnow() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )
    assert manager.is_token_valid() is False


def test_is_token_valid_when_missing_token():
    """is_token_valid returns False when no access token exists."""
    manager, _api = make_manager()
    assert manager.is_token_valid() is False


def test_handle_refresh_flow_raises_without_refresh_token():
    """_handle_refresh_flow fails fast if no refresh token is available."""
    manager, _api = make_manager()
    with pytest.raises(LoginError, match="No refresh token available"):
        manager._handle_refresh_flow()


def test_handle_refresh_flow_posts_with_authorization():
    """_handle_refresh_flow sends the correct Authorization header."""
    manager, api = make_manager()
    api.account_data = AccountData({"refresh_token": "refresh", "token_type": "Bearer"})

    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 400

    mock_scraper = MagicMock()
    mock_scraper.post.return_value = mock_response

    with patch.object(manager, "create_auth_scraper", return_value=mock_scraper), patch.object(
        manager, "_finalize_session_from_tokens"
    ):
        with pytest.raises(LoginError) as exc_info:
            manager._handle_refresh_flow()
        assert exc_info.value.error_code == "REFRESH_TOKEN_EXPIRED"

    call_args = mock_scraper.post.call_args
    assert call_args[1]["headers"]["Authorization"] == AUTHORIZATION
    assert call_args[1]["headers"]["User-Agent"] == api.CRUNCHYROLL_UA


def test_request_device_code_posts_to_device_code_endpoint():
    """request_device_code POSTs to the device-code endpoint."""
    manager, _api = make_manager()
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"device_code": "d", "user_code": "u"}

    mock_scraper = MagicMock()
    mock_scraper.post.return_value = mock_response

    with patch.object(manager, "create_auth_scraper", return_value=mock_scraper):
        result = manager.request_device_code()

    assert result["device_code"] == "d"
    call_args = mock_scraper.post.call_args
    assert call_args[1]["url"] == "https://www.crunchyroll.com/auth/v1/device/code"


def test_poll_device_token_posts_to_device_token_endpoint():
    """poll_device_token POSTs the device code to the token endpoint."""
    manager, _api = make_manager()
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"access_token": "a", "refresh_token": "r"}'
    mock_response.json.return_value = {"access_token": "a", "refresh_token": "r"}

    mock_scraper = MagicMock()
    mock_scraper.post.return_value = mock_response

    with patch.object(manager, "create_auth_scraper", return_value=mock_scraper):
        result = manager.poll_device_token("dev-code-123")

    assert result["status"] == "success"
    assert result["data"]["access_token"] == "a"
    call_args = mock_scraper.post.call_args
    assert call_args[1]["url"] == "https://www.crunchyroll.com/auth/v1/device/token"
    assert call_args[1]["json"]["device_code"] == "dev-code-123"


def test_finalize_session_from_tokens_updates_api_state():
    """_finalize_session_from_tokens writes tokens back to the API state."""
    manager, api = make_manager()

    manager._finalize_session_from_tokens(
        {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "token_type": "Bearer",
            "expires_in": 3600,
        },
        action="login",
    )

    assert api.account_data.access_token == "new_access"
    assert api.account_data.refresh_token == "new_refresh"
    assert api.api_headers["Authorization"] == "Bearer new_access"


def test_create_session_delegates_to_login_flow():
    """create_session(action='login') triggers the device login flow."""
    manager, _api = make_manager()
    with patch.object(manager, "_handle_login_flow") as mock_login:
        manager.create_session(action="login")
        mock_login.assert_called_once()


def test_create_session_refresh_falls_back_to_login_on_expired_token():
    """create_session(action='refresh') falls back to login when refresh token expired."""
    manager, api = make_manager()
    error = LoginError("Refresh token expired", error_code="REFRESH_TOKEN_EXPIRED")

    with patch.object(manager, "_handle_refresh_flow", side_effect=error), patch.object(
        manager, "_handle_login_flow"
    ) as mock_login, patch.object(api.account_data, "delete_storage") as mock_delete, patch(
        "resources.lib.auth.xbmcgui.Dialog"
    ):
        manager.create_session(action="refresh")

    mock_delete.assert_called_once()
    mock_login.assert_called_once()
