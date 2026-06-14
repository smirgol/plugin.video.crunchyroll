"""
Unit tests for API exception handling

Tests that LoginError exceptions with error_code are properly preserved
during token refresh flows and not wrapped in generic exceptions.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from resources.lib.api import API
from resources.lib.models.account import AccountData
from resources.lib.models.exceptions import LoginError


class TestRefreshFlowExceptionHandling:
    """Test exception handling in _handle_refresh_flow"""

    def setup_method(self):
        """Setup API instance with mocked dependencies"""
        with patch("resources.lib.api.default_request_headers"), patch("resources.lib.globals.G"):
            self.api = API()
            self.api.account_data = AccountData(
                {"refresh_token": "test_refresh_token", "token_type": "Bearer", "access_token": "test_access_token"}
            )

    def test_refresh_flow_preserves_refresh_token_expired_error(self):
        """Test that REFRESH_TOKEN_EXPIRED error_code is preserved"""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400

        mock_scraper = Mock()
        mock_scraper.post.return_value = mock_response

        with patch.object(self.api, "create_auth_scraper", return_value=mock_scraper):
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            assert exc_info.value.error_code == "REFRESH_TOKEN_EXPIRED"
            assert "Refresh token expired" in str(exc_info.value)

    def test_refresh_flow_preserves_server_error(self):
        """Test that SERVER_ERROR error_code is preserved"""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500

        mock_scraper = Mock()
        mock_scraper.post.return_value = mock_response

        with patch.object(self.api, "create_auth_scraper", return_value=mock_scraper):
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            assert exc_info.value.error_code == "SERVER_ERROR"

    def test_refresh_flow_network_error_handling(self):
        """Test that network errors are wrapped in LoginError without error_code"""
        mock_scraper = Mock()
        mock_scraper.post.side_effect = requests.exceptions.ConnectionError("Network down")

        with patch.object(self.api, "create_auth_scraper", return_value=mock_scraper):
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            assert exc_info.value.error_code is None
            assert "Network error" in str(exc_info.value)

    def test_refresh_flow_unexpected_error_handling(self):
        """Test that unexpected errors are wrapped in LoginError without error_code"""
        mock_scraper = Mock()
        mock_scraper.post.side_effect = ValueError("Unexpected")

        with patch.object(self.api, "create_auth_scraper", return_value=mock_scraper):
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            assert exc_info.value.error_code is None
            assert "Unexpected error during token refresh" in str(exc_info.value)

    def test_refresh_flow_cloudscraper_login_error_preserved(self):
        """Test that LoginError from cloudscraper is re-raised as-is"""
        mock_scraper = Mock()
        login_error = LoginError("Custom error", error_code="CUSTOM_ERROR")
        mock_scraper.post.side_effect = login_error

        with patch.object(self.api, "create_auth_scraper", return_value=mock_scraper):
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            assert exc_info.value.error_code == "CUSTOM_ERROR"
            assert str(exc_info.value) == "Custom error"


class TestProfileRefreshFlowExceptionHandling:
    """Test exception handling in _handle_profile_refresh_flow"""

    def setup_method(self):
        """Setup API instance with mocked dependencies"""
        with patch("resources.lib.api.default_request_headers"), patch("resources.lib.globals.G"):
            self.api = API()
            self.api.account_data = AccountData(
                {"refresh_token": "test_refresh_token", "token_type": "Bearer", "access_token": "test_access_token"}
            )

    def test_profile_refresh_preserves_login_error(self):
        """Test that LoginError with error_code is preserved during profile refresh"""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400

        mock_scraper = Mock()
        mock_scraper.post.return_value = mock_response

        with patch.object(self.api, "create_auth_scraper", return_value=mock_scraper):
            with pytest.raises(LoginError):
                self.api._handle_profile_refresh_flow("profile_123")

    def test_profile_refresh_network_error_handling(self):
        """Test that network errors during profile refresh are handled correctly"""
        mock_scraper = Mock()
        mock_scraper.post.side_effect = requests.exceptions.Timeout("Timeout")

        with patch.object(self.api, "create_auth_scraper", return_value=mock_scraper):
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_profile_refresh_flow("profile_123")

            assert "Network connection failed" in str(exc_info.value)

    def test_profile_refresh_cloudscraper_login_error_preserved(self):
        """Test that LoginError from cloudscraper is re-raised during profile refresh"""
        mock_scraper = Mock()
        login_error = LoginError("Profile error", error_code="PROFILE_ERROR")
        mock_scraper.post.side_effect = login_error

        with patch.object(self.api, "create_auth_scraper", return_value=mock_scraper):
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_profile_refresh_flow("profile_123")

            assert exc_info.value.error_code == "PROFILE_ERROR"
            assert str(exc_info.value) == "Profile error"


class TestCreateSessionRefreshTokenExpiredHandling:
    """Test that create_session correctly handles REFRESH_TOKEN_EXPIRED error_code"""

    def setup_method(self):
        """Setup API instance with mocked dependencies"""
        with patch("resources.lib.api.default_request_headers"), patch("resources.lib.globals.G"):
            self.api = API()
            self.api.account_data = AccountData(
                {"refresh_token": "test_refresh_token", "token_type": "Bearer", "access_token": "test_access_token"}
            )

    def test_create_session_triggers_device_flow_on_expired_refresh_token(self):
        """Test that create_session falls back to device flow when refresh token expires"""
        refresh_error = LoginError("Refresh token expired", error_code="REFRESH_TOKEN_EXPIRED")
        mock_login_flow = Mock()

        with patch.object(self.api, "_handle_refresh_flow", side_effect=refresh_error), patch.object(
            self.api, "_handle_login_flow", mock_login_flow
        ), patch("xbmcgui.Dialog") as mock_dialog, patch.object(self.api.account_data, "delete_storage"):
            self.api.create_session(action="refresh")

            mock_dialog.return_value.ok.assert_called_once()
            self.api.account_data.delete_storage.assert_called_once()
            mock_login_flow.assert_called_once()

    def test_create_session_reraises_other_login_errors(self):
        """Test that create_session re-raises LoginError without REFRESH_TOKEN_EXPIRED"""
        refresh_error = LoginError("Network error")

        with patch.object(self.api, "_handle_refresh_flow", side_effect=refresh_error):
            with pytest.raises(LoginError) as exc_info:
                self.api.create_session(action="refresh")

            assert str(exc_info.value) == "Network error"
            assert exc_info.value.error_code is None
