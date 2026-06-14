"""
Focused unit tests for resources.lib.auth.AuthManager.

These tests exercise the extracted authentication manager directly without
relying on the API facade wrappers.
"""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest

from resources.lib.auth import AuthManager, get_date, str_to_date
from resources.lib.models.account import AccountData, ProfileData
from resources.lib.models.exceptions import LoginError


class _FakeAPI:
    """Lightweight stand-in for resources.lib.api.API."""

    CRUNCHYROLL_UA = "Crunchyroll/Test"

    def __init__(self):
        self.account_data = AccountData({})
        self.profile_data = ProfileData({})
        self.api_headers = {}
        self.refresh_attempts = 0

    def make_unauthenticated_request(self, method, url, headers=None, **_kwargs):
        # Return minimal data needed by _finalize_session_from_tokens
        if "index" in url:
            return {"account_id": "acct_123"}
        if "accounts/v1/me/profile" in url:
            return {"username": "testuser"}
        if "multiprofile" in url:
            return {"profiles": [{"profile_id": "p1", "username": "u1"}]}
        return {}

    def create_auth_scraper(self):
        return Mock()

    def _handle_login_flow(self):
        pass

    def _handle_refresh_flow(self):
        pass

    def _handle_profile_refresh_flow(self, profile_id):
        pass

    def _handle_device_code_flow(self):
        pass

    def _process_device_token_response(self, r):
        return {"status": "pending"}

    def _finalize_session_from_tokens(self, token_response, action="login", profile_id=None):
        pass


@pytest.fixture
def auth():
    fake_api = _FakeAPI()
    with patch("resources.lib.auth.G"):
        yield AuthManager(fake_api)


class TestAuthManagerTokenValidity:
    def test_token_valid_when_future_expiry(self, auth):
        auth.api.account_data = AccountData(
            {
                "access_token": "token",
                "expires": f"{get_date() + timedelta(minutes=5):%Y-%m-%dT%H:%M:%SZ}",
            }
        )
        assert auth.is_token_valid() is True

    def test_token_invalid_when_past_expiry(self, auth):
        auth.api.account_data = AccountData(
            {
                "access_token": "token",
                "expires": f"{get_date() - timedelta(minutes=5):%Y-%m-%dT%H:%M:%SZ}",
            }
        )
        assert auth.is_token_valid() is False

    def test_token_invalid_without_access_token(self, auth):
        auth.api.account_data = AccountData({})
        assert auth.is_token_valid() is False

    def test_token_invalid_without_expires(self, auth):
        auth.api.account_data = AccountData({"access_token": "token"})
        assert auth.is_token_valid() is False

    def test_token_invalid_when_within_buffer(self, auth):
        auth.api.account_data = AccountData(
            {
                "access_token": "token",
                "expires": f"{get_date() + timedelta(seconds=30):%Y-%m-%dT%H:%M:%SZ}",
            }
        )
        assert auth.is_token_valid() is False


class TestAuthManagerFinalizeSession:
    def test_finalize_session_updates_account_data(self, auth):
        token_response = {
            "access_token": "acc",
            "token_type": "Bearer",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        auth._finalize_session_from_tokens(token_response, action="login")

        assert auth.api.account_data.access_token == "acc"
        assert auth.api.account_data.refresh_token == "ref"
        assert auth.api.account_data.token_type == "Bearer"
        assert auth.api.account_data.account_id == "acct_123"
        assert auth.api.account_data.username == "testuser"

    def test_finalize_session_calculates_expiration(self, auth):
        token_response = {
            "access_token": "acc",
            "token_type": "Bearer",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        auth._finalize_session_from_tokens(token_response, action="login")

        expiry = str_to_date(auth.api.account_data.expires)
        assert expiry > get_date()
        # 60s buffer is applied during validation, not during storage
        assert (expiry - get_date()).total_seconds() > 3500

    def test_finalize_session_sets_api_headers(self, auth):
        token_response = {
            "access_token": "acc",
            "token_type": "Bearer",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        auth._finalize_session_from_tokens(token_response, action="login")

        assert auth.api.api_headers["Authorization"] == "Bearer acc"
        assert "User-Agent" in auth.api.api_headers

    def test_finalize_session_with_missing_token_field_raises_login_error(self, auth):
        with pytest.raises(LoginError):
            auth._finalize_session_from_tokens({"expires_in": 3600}, action="login")

    def test_finalize_session_refresh_resets_refresh_attempts(self, auth):
        auth.api.refresh_attempts = 2
        token_response = {
            "access_token": "acc",
            "token_type": "Bearer",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        auth._finalize_session_from_tokens(token_response, action="refresh")
        assert auth.api.refresh_attempts == 0


class TestAuthManagerRefreshFlow:
    def test_refresh_flow_raises_without_refresh_token(self, auth):
        auth.api.account_data = AccountData({"access_token": "token"})
        with pytest.raises(LoginError, match="No refresh token available"):
            auth._handle_refresh_flow()

    def test_refresh_flow_success(self, auth):
        auth.api.account_data = AccountData({"refresh_token": "ref", "access_token": "token"})
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "access_token": "new",
            "token_type": "Bearer",
            "refresh_token": "new_ref",
            "expires_in": 3600,
        }
        mock_scraper = Mock()
        mock_scraper.post.return_value = mock_response
        fake_api = auth.api
        fake_api.create_auth_scraper = Mock(return_value=mock_scraper)

        with patch.object(fake_api, "_finalize_session_from_tokens") as mock_finalize:
            auth._handle_refresh_flow()
            mock_finalize.assert_called_once()

    def test_refresh_flow_400_raises_refresh_token_expired(self, auth):
        auth.api.account_data = AccountData({"refresh_token": "ref", "access_token": "token"})
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400
        mock_scraper = Mock()
        mock_scraper.post.return_value = mock_response
        auth.api.create_auth_scraper = Mock(return_value=mock_scraper)

        with pytest.raises(LoginError) as exc_info:
            auth._handle_refresh_flow()

        assert exc_info.value.error_code == "REFRESH_TOKEN_EXPIRED"


class TestAuthManagerProfileRefreshFlow:
    def test_profile_refresh_requires_profile_id(self, auth):
        auth.api.account_data = AccountData({"refresh_token": "ref", "access_token": "token"})
        with pytest.raises(LoginError, match="Profile ID required"):
            auth._handle_profile_refresh_flow(None)

    def test_profile_refresh_requires_refresh_token(self, auth):
        auth.api.account_data = AccountData({"access_token": "token"})
        with pytest.raises(LoginError, match="No refresh token available"):
            auth._handle_profile_refresh_flow("p1")


class TestAuthManagerDeviceCodeFlow:
    def test_request_device_code_success(self, auth):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"user_code": "ABCD", "device_code": "dc"}
        mock_scraper = Mock()
        mock_scraper.post.return_value = mock_response
        auth.api.create_auth_scraper = Mock(return_value=mock_scraper)

        result = auth.request_device_code()
        assert result["user_code"] == "ABCD"
        assert result["device_code"] == "dc"

    def test_poll_device_token_returns_pending(self, auth):
        auth.api._process_device_token_response = Mock(return_value={"status": "pending"})
        mock_scraper = Mock()
        auth.api.create_auth_scraper = Mock(return_value=mock_scraper)

        result = auth.poll_device_token("dc")
        assert result["status"] == "pending"
