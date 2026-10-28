"""Focused unit tests for resources.lib.auth.AuthManager.

These tests exercise AuthManager directly using a lightweight fake API that
provides the same attributes/methods the real API exposes to AuthManager.
This avoids the circular pass-through that existed before Phase 9b.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from resources.lib.auth import AUTHORIZATION, PASSTOKEN_ENDPOINT, TOKEN_ENDPOINT, AuthManager
from resources.lib.models.account import AccountData, ProfileData
from resources.lib.models.exceptions import PROFILE_PIN_INVALID, LoginError


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


def _response(status_code: int, ok: bool = False, body=None, json_error=None):
    response = MagicMock()
    response.ok = ok
    response.status_code = status_code
    response.text = "<html>blocked</html>" if json_error else str(body or {})
    if json_error:
        response.json.side_effect = json_error
    else:
        response.json.return_value = body or {}
    return response


def _scraper_returning(status_code: int, ok: bool = False, body=None, json_error=None):
    scraper = MagicMock()
    scraper.post.return_value = _response(status_code, ok=ok, body=body, json_error=json_error)
    return scraper


def _manager_with_refresh_token():
    manager, api = make_manager()
    api.account_data = AccountData({"refresh_token": "refresh", "token_type": "Bearer"})
    return manager, api


def test_handle_refresh_flow_without_refresh_token_sets_error_code():
    """A missing refresh token is flagged with NO_REFRESH_TOKEN so create_session can fall back."""
    manager, _api = make_manager()
    with pytest.raises(LoginError) as exc_info:
        manager._handle_refresh_flow()
    assert exc_info.value.error_code == "NO_REFRESH_TOKEN"


def test_handle_refresh_flow_401_is_treated_as_expired_refresh_token():
    """HTTP 401 on refresh means the refresh token is no longer accepted."""
    manager, _api = _manager_with_refresh_token()
    with patch.object(manager, "create_auth_scraper", return_value=_scraper_returning(401)):
        with pytest.raises(LoginError) as exc_info:
            manager._handle_refresh_flow()
    assert str(exc_info.value) == "Refresh token expired"
    assert exc_info.value.error_code == "REFRESH_TOKEN_EXPIRED"


def test_handle_refresh_flow_403_stays_generic_failure():
    """HTTP 403 may be a Cloudflare block and must not be reported as an expired token."""
    manager, _api = _manager_with_refresh_token()
    with patch.object(manager, "create_auth_scraper", return_value=_scraper_returning(403)):
        with pytest.raises(LoginError) as exc_info:
            manager._handle_refresh_flow()
    assert str(exc_info.value) == "Token refresh failed"
    assert exc_info.value.error_code is None


@pytest.mark.parametrize("oauth_error", ["invalid_client", "invalid_grant"])
def test_handle_refresh_flow_403_with_oauth_error_is_treated_as_expired_refresh_token(oauth_error):
    """A 4xx carrying an OAuth rejection body (e.g. after client credential rotation) means re-login."""
    manager, _api = _manager_with_refresh_token()
    scraper = _scraper_returning(403, body={"error": oauth_error})
    with patch.object(manager, "create_auth_scraper", return_value=scraper):
        with pytest.raises(LoginError) as exc_info:
            manager._handle_refresh_flow()
    assert exc_info.value.error_code == "REFRESH_TOKEN_EXPIRED"


def test_handle_refresh_flow_403_with_non_json_body_stays_generic_failure():
    """A non-JSON 403 body (e.g. Cloudflare HTML) is parsed safely and stays a generic failure."""
    manager, _api = _manager_with_refresh_token()
    scraper = _scraper_returning(403, json_error=ValueError("not json"))
    with patch.object(manager, "create_auth_scraper", return_value=scraper):
        with pytest.raises(LoginError) as exc_info:
            manager._handle_refresh_flow()
    assert str(exc_info.value) == "Token refresh failed"
    assert exc_info.value.error_code is None


def test_handle_refresh_flow_logs_failed_status_without_refresh_token():
    """A non-ok refresh response is logged at LOGERROR with its status code, never with the refresh token."""
    import resources.lib.auth as auth_module

    manager, api = make_manager()
    api.account_data = AccountData({"refresh_token": "secret-refresh-token-xyz", "token_type": "Bearer"})
    scraper = _scraper_returning(403, body={"error": "access_denied"})

    with patch.object(manager, "create_auth_scraper", return_value=scraper), patch(
        "resources.lib.auth.crunchy_log"
    ) as mock_log:
        with pytest.raises(LoginError):
            manager._handle_refresh_flow()

    error_logs = [
        str(c)
        for c in mock_log.call_args_list
        if auth_module.xbmc.LOGERROR in c[0] or c[1].get("loglevel") == auth_module.xbmc.LOGERROR
    ]
    assert any("403" in log for log in error_logs)
    assert all("secret-refresh-token-xyz" not in str(c) for c in mock_log.call_args_list)


def test_handle_refresh_flow_5xx_is_server_error():
    """HTTP 5xx on refresh keeps the SERVER_ERROR code."""
    manager, _api = _manager_with_refresh_token()
    with patch.object(manager, "create_auth_scraper", return_value=_scraper_returning(503)):
        with pytest.raises(LoginError) as exc_info:
            manager._handle_refresh_flow()
    assert exc_info.value.error_code == "SERVER_ERROR"


def test_handle_refresh_flow_network_error_has_no_error_code():
    """Network failures during refresh carry no error code."""
    import requests

    manager, _api = _manager_with_refresh_token()
    scraper = MagicMock()
    scraper.post.side_effect = requests.exceptions.ConnectionError("down")
    with patch.object(manager, "create_auth_scraper", return_value=scraper):
        with pytest.raises(LoginError) as exc_info:
            manager._handle_refresh_flow()
    assert exc_info.value.error_code is None


def test_create_session_refresh_falls_back_to_login_without_refresh_token():
    """create_session(action='refresh') falls back to login when no refresh token is stored."""
    manager, api = make_manager()
    error = LoginError("No refresh token available", error_code="NO_REFRESH_TOKEN")

    with patch.object(manager, "_handle_refresh_flow", side_effect=error), patch.object(
        manager, "_handle_login_flow"
    ) as mock_login, patch.object(api.account_data, "delete_storage") as mock_delete, patch(
        "resources.lib.auth.xbmcgui.Dialog"
    ):
        manager.create_session(action="refresh")

    mock_delete.assert_called_once()
    mock_login.assert_called_once()


@pytest.mark.parametrize(
    "error",
    [
        LoginError("Token refresh failed"),
        LoginError("Server error", error_code="SERVER_ERROR"),
        LoginError("Network error"),
    ],
    ids=["403-generic", "5xx-server", "network"],
)
def test_create_session_refresh_reraises_non_auth_errors(error):
    """Transient or ambiguous refresh failures propagate instead of forcing a new login."""
    manager, api = make_manager()

    with patch.object(manager, "_handle_refresh_flow", side_effect=error), patch.object(
        manager, "_handle_login_flow"
    ) as mock_login, patch.object(api.account_data, "delete_storage") as mock_delete, patch(
        "resources.lib.auth.xbmcgui.Dialog"
    ):
        with pytest.raises(LoginError) as exc_info:
            manager.create_session(action="refresh")

    assert exc_info.value is error
    mock_delete.assert_not_called()
    mock_login.assert_not_called()


def test_start_with_legacy_account_data_deletes_storage_and_logs_in():
    """Legacy stored sessions are discarded and a fresh login runs without attempting a refresh."""
    manager, api = make_manager()
    api.args.get_arg.return_value = False
    legacy = {"user_agent_type": "mobile", "refresh_token": "old", "access_token": "old"}

    with patch.object(AccountData, "load_from_storage", return_value=legacy), patch.object(
        ProfileData, "load_from_storage", return_value={}
    ), patch.object(AccountData, "delete_storage") as mock_delete, patch.object(
        manager, "_handle_refresh_flow"
    ) as mock_refresh, patch.object(manager, "_handle_login_flow") as mock_login:
        manager.start()

    mock_refresh.assert_not_called()
    mock_delete.assert_called_once_with(api.args.addon)
    mock_login.assert_called_once()


def test_handle_refresh_flow_400_is_treated_as_expired_refresh_token():
    """HTTP 400 on refresh means the refresh token is no longer accepted."""
    manager, _api = _manager_with_refresh_token()
    with patch.object(manager, "create_auth_scraper", return_value=_scraper_returning(400)):
        with pytest.raises(LoginError) as exc_info:
            manager._handle_refresh_flow()
    assert exc_info.value.error_code == "REFRESH_TOKEN_EXPIRED"


def test_create_session_refresh_fallback_shows_session_expired_dialog():
    """The refresh fallback tells the user via dialog 30401 that a new login is required."""
    manager, api = make_manager()
    api.args.addon.getLocalizedString.side_effect = lambda string_id: f"String_{string_id}"
    error = LoginError("Refresh token expired", error_code="REFRESH_TOKEN_EXPIRED")

    with patch.object(manager, "_handle_refresh_flow", side_effect=error), patch.object(
        manager, "_handle_login_flow"
    ), patch.object(AccountData, "delete_storage"), patch("resources.lib.auth.xbmcgui.Dialog") as mock_dialog:
        manager.create_session(action="refresh")

    mock_dialog.return_value.ok.assert_called_once_with(api.args.addon_name, "String_30401")


def test_create_session_refresh_fallback_does_not_retry_rejected_refresh_token():
    """After a rejected refresh, the login flow starts from clean in-memory state and goes straight to device code."""
    manager, api = _manager_with_refresh_token()
    error = LoginError("Refresh token expired", error_code="REFRESH_TOKEN_EXPIRED")

    with patch.object(manager, "_handle_refresh_flow", side_effect=error) as mock_refresh, patch.object(
        manager, "_handle_device_code_flow"
    ) as mock_device_flow, patch.object(AccountData, "delete_storage"), patch("resources.lib.auth.xbmcgui.Dialog"):
        manager.create_session(action="refresh")

    assert mock_refresh.call_count == 1
    mock_device_flow.assert_called_once()
    assert not api.account_data.refresh_token


# --- Profile switch with PIN (passtoken) ---

PROFILE_TOKENS = {"access_token": "profile_access", "refresh_token": "profile_refresh", "expires_in": 3600}
WRONG_PIN_BODY = {
    "code": "auth.obtain_pass_token.failed_pass_token_credentials",
    "context": [{"code": "auth.obtain_pass_token.passtoken_creation_invalid_credential", "field": "profile_pin"}],
}
INVALID_PIN_LENGTH_BODY = {
    "code": "auth.obtain_pass_token.data_validation_error",
    "context": [
        {
            "code": "auth.obtain_pass_token.invalid_length",
            "field": "value",
            "violated_constraints": {"profile_pin_length": "must be 4 digits"},
        }
    ],
}


def _expires_in(hours: int) -> str:
    from datetime import datetime, timedelta

    return (datetime.utcnow() + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _manager_for_profile_switch(access_token_valid: bool = True):
    manager, api = make_manager()
    api.account_data = AccountData(
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "token_type": "Bearer",
            "expires": _expires_in(1 if access_token_valid else -1),
        }
    )
    return manager, api


def _switch_profile_with_pin(manager, scraper, pin="1234"):
    with patch.object(manager, "create_auth_scraper", return_value=scraper), patch.object(
        manager, "_finalize_session_from_tokens"
    ) as mock_finalize:
        manager.create_session(action="refresh_profile", profile_id="p1", profile_pin=pin)
    return mock_finalize


def test_profile_switch_with_pin_sends_pass_token_to_token_request():
    """A PIN is exchanged for a passtoken, which is sent as CrPassToken header on the profile token request."""
    manager, _api = _manager_for_profile_switch()
    scraper = MagicMock()
    scraper.post.side_effect = [
        _response(200, ok=True, body={"code": "pass-123"}),
        _response(200, ok=True, body=PROFILE_TOKENS),
    ]

    mock_finalize = _switch_profile_with_pin(manager, scraper)

    passtoken_call, token_call = scraper.post.call_args_list
    assert passtoken_call[1]["url"] == PASSTOKEN_ENDPOINT % "p1"
    assert passtoken_call[1]["headers"]["Authorization"] == "Bearer access"
    assert passtoken_call[1]["json"] == {"credential_type": "profile_pin", "profile_id": "p1", "value": "1234"}
    assert token_call[1]["url"] == TOKEN_ENDPOINT
    assert token_call[1]["headers"]["CrPassToken"] == "pass-123"
    assert token_call[1]["data"]["grant_type"] == "refresh_token_profile_id"
    assert token_call[1]["data"]["profile_id"] == "p1"
    mock_finalize.assert_called_once_with(PROFILE_TOKENS, action="refresh_profile", profile_id="p1")


@pytest.mark.parametrize(
    ("status", "body"),
    [(401, WRONG_PIN_BODY), (400, INVALID_PIN_LENGTH_BODY)],
    ids=["401-wrong-pin", "400-invalid-length"],
)
def test_profile_switch_with_wrong_pin_raises_profile_pin_invalid(status, body):
    """Wrong-PIN and PIN-validation payloads are reported as PROFILE_PIN_INVALID and no profile token is requested."""
    manager, _api = _manager_for_profile_switch()
    scraper = _scraper_returning(status, body=body)

    with pytest.raises(LoginError) as exc_info:
        _switch_profile_with_pin(manager, scraper)

    assert exc_info.value.error_code == PROFILE_PIN_INVALID
    assert scraper.post.call_count == 1


@pytest.mark.parametrize(
    "response",
    [
        _response(401, body={"code": "auth.some_other_failure"}),
        _response(403, json_error=ValueError("not json")),
    ],
    ids=["401-other-code", "403-non-json"],
)
def test_profile_switch_passtoken_failure_without_pin_code_is_generic(response):
    """A passtoken rejection without the wrong-PIN payload is a generic failure, not PROFILE_PIN_INVALID."""
    manager, _api = _manager_for_profile_switch()
    scraper = MagicMock()
    scraper.post.return_value = response

    with pytest.raises(LoginError) as exc_info:
        _switch_profile_with_pin(manager, scraper)

    assert str(exc_info.value) == "Profile PIN verification failed"
    assert exc_info.value.error_code is None
    assert scraper.post.call_count == 1


def test_profile_switch_passtoken_5xx_is_server_error():
    """HTTP 5xx on the passtoken request keeps the SERVER_ERROR code."""
    manager, _api = _manager_for_profile_switch()
    scraper = _scraper_returning(503)

    with pytest.raises(LoginError) as exc_info:
        _switch_profile_with_pin(manager, scraper)

    assert exc_info.value.error_code == "SERVER_ERROR"
    assert scraper.post.call_count == 1


def test_profile_switch_passtoken_network_error_raises_login_error():
    """Network failures on the passtoken request surface as LoginError."""
    import requests

    manager, _api = _manager_for_profile_switch()
    scraper = MagicMock()
    scraper.post.side_effect = requests.exceptions.ConnectionError("down")

    with pytest.raises(LoginError) as exc_info:
        _switch_profile_with_pin(manager, scraper)

    assert str(exc_info.value) == "Network connection failed during profile switch"
    assert exc_info.value.error_code != PROFILE_PIN_INVALID


@pytest.mark.parametrize(
    "response",
    [
        _response(200, ok=True, body={}),
        _response(200, ok=True, json_error=ValueError("not json")),
    ],
    ids=["no-code", "non-json"],
)
def test_profile_switch_passtoken_ok_without_code_does_not_switch(response):
    """Without a passtoken code there is no proof of the PIN, so no profile token is requested."""
    manager, _api = _manager_for_profile_switch()
    scraper = MagicMock()
    scraper.post.return_value = response

    with pytest.raises(LoginError) as exc_info:
        _switch_profile_with_pin(manager, scraper)

    assert exc_info.value.error_code != PROFILE_PIN_INVALID
    assert scraper.post.call_count == 1


def test_profile_switch_with_pin_refreshes_expired_access_token_first():
    """An access token that expired while the PIN dialog was open is refreshed before the passtoken request."""
    manager, api = _manager_for_profile_switch(access_token_valid=False)

    def refresh():
        api.account_data = AccountData(
            {"access_token": "fresh", "refresh_token": "refresh2", "token_type": "Bearer", "expires": _expires_in(1)}
        )

    scraper = MagicMock()
    scraper.post.side_effect = [
        _response(200, ok=True, body={"code": "pass-123"}),
        _response(200, ok=True, body=PROFILE_TOKENS),
    ]

    with patch.object(manager, "_handle_refresh_flow", side_effect=refresh) as mock_refresh:
        _switch_profile_with_pin(manager, scraper)

    mock_refresh.assert_called_once()
    passtoken_call = scraper.post.call_args_list[0]
    assert passtoken_call[1]["headers"]["Authorization"] == "Bearer fresh"
    token_call = scraper.post.call_args_list[1]
    assert token_call[1]["data"]["refresh_token"] == "refresh2"
    assert token_call[1]["headers"]["CrPassToken"] == "pass-123"


def test_profile_switch_without_pin_skips_passtoken():
    """Without a PIN only the profile token request is sent, without CrPassToken header."""
    manager, _api = _manager_for_profile_switch()
    scraper = _scraper_returning(200, ok=True, body=PROFILE_TOKENS)

    _switch_profile_with_pin(manager, scraper, pin=None)

    scraper.post.assert_called_once()
    assert scraper.post.call_args[1]["url"] == TOKEN_ENDPOINT
    assert "CrPassToken" not in scraper.post.call_args[1]["headers"]
