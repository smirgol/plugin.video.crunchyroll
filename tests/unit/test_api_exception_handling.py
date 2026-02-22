"""
Unit tests for API exception handling

Tests that LoginError exceptions with error_code are properly preserved
during token refresh flows and not wrapped in generic exceptions.
"""

from unittest.mock import Mock, patch

import pytest
import requests

from resources.lib.api import API
from resources.lib.model import LoginError, AccountData


class TestRefreshFlowExceptionHandling:
    """Test exception handling in _handle_refresh_flow"""

    def setup_method(self):
        """Setup API instance with mocked dependencies"""
        with patch('resources.lib.api.default_request_headers'), \
             patch('resources.lib.globals.G'):
            self.api = API()
            self.api.account_data = AccountData({
                'refresh_token': 'test_refresh_token',
                'token_type': 'Bearer',
                'access_token': 'test_access_token'
            })

    def test_refresh_flow_preserves_refresh_token_expired_error(self):
        """Test that REFRESH_TOKEN_EXPIRED error_code is preserved"""
        # Mock HTTP response with 400 status
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400

        # Mock both cloudscraper (returns None to skip) and requests.post
        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', return_value=mock_response):

            # Should raise LoginError with error_code="REFRESH_TOKEN_EXPIRED"
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            # Verify error_code is preserved
            assert exc_info.value.error_code == "REFRESH_TOKEN_EXPIRED"
            assert "Refresh token expired" in str(exc_info.value)

    def test_refresh_flow_preserves_server_error(self):
        """Test that SERVER_ERROR error_code is preserved"""
        # Mock HTTP response with 500 status
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500

        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', return_value=mock_response):

            # Should raise LoginError with error_code="SERVER_ERROR"
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            # Verify error_code is preserved
            assert exc_info.value.error_code == "SERVER_ERROR"

    def test_refresh_flow_network_error_handling(self):
        """Test that network errors are wrapped in LoginError without error_code"""
        # Mock network error
        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', side_effect=requests.exceptions.ConnectionError("Network down")):

            # Should raise LoginError without specific error_code
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            # Should NOT have error_code (network errors are generic)
            assert exc_info.value.error_code is None
            assert "Network error" in str(exc_info.value)

    def test_refresh_flow_unexpected_error_handling(self):
        """Test that unexpected errors are wrapped in LoginError without error_code"""
        # Mock unexpected error
        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', side_effect=ValueError("Unexpected")):

            # Should raise LoginError without specific error_code
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            # Should NOT have error_code
            assert exc_info.value.error_code is None
            assert "Unexpected error during token refresh" in str(exc_info.value)

    def test_refresh_flow_cloudscraper_login_error_preserved(self):
        """Test that LoginError from cloudscraper is re-raised as-is"""
        # Mock cloudscraper that raises LoginError with error_code
        mock_scraper = Mock()
        login_error = LoginError("Custom error", error_code="CUSTOM_ERROR")
        mock_scraper.post.side_effect = login_error

        with patch.object(self.api, 'create_auth_scraper', return_value=mock_scraper):

            # Should re-raise the same LoginError
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_refresh_flow()

            # Verify it's the SAME error object with error_code intact
            assert exc_info.value.error_code == "CUSTOM_ERROR"
            assert str(exc_info.value) == "Custom error"


class TestProfileRefreshFlowExceptionHandling:
    """Test exception handling in _handle_profile_refresh_flow"""

    def setup_method(self):
        """Setup API instance with mocked dependencies"""
        with patch('resources.lib.api.default_request_headers'), \
             patch('resources.lib.globals.G'):
            self.api = API()
            self.api.account_data = AccountData({
                'refresh_token': 'test_refresh_token',
                'token_type': 'Bearer',
                'access_token': 'test_access_token'
            })

    def test_profile_refresh_preserves_login_error(self):
        """Test that LoginError with error_code is preserved during profile refresh"""
        # Mock HTTP response with 400 status
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 400

        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', return_value=mock_response):

            # Should raise LoginError (profile refresh doesn't set error_code on 400)
            with pytest.raises(LoginError):
                self.api._handle_profile_refresh_flow("profile_123")

    def test_profile_refresh_network_error_handling(self):
        """Test that network errors during profile refresh are handled correctly"""
        # Mock network error
        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', side_effect=requests.exceptions.Timeout("Timeout")):

            # Should raise LoginError
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_profile_refresh_flow("profile_123")

            assert "Network connection failed" in str(exc_info.value)

    def test_profile_refresh_cloudscraper_login_error_preserved(self):
        """Test that LoginError from cloudscraper is re-raised during profile refresh"""
        # Mock cloudscraper that raises LoginError with error_code
        mock_scraper = Mock()
        login_error = LoginError("Profile error", error_code="PROFILE_ERROR")
        mock_scraper.post.side_effect = login_error

        with patch.object(self.api, 'create_auth_scraper', return_value=mock_scraper):

            # Should re-raise the same LoginError
            with pytest.raises(LoginError) as exc_info:
                self.api._handle_profile_refresh_flow("profile_123")

            # Verify error_code is preserved
            assert exc_info.value.error_code == "PROFILE_ERROR"
            assert str(exc_info.value) == "Profile error"


class TestCreateSessionRefreshTokenExpiredHandling:
    """Test that create_session correctly handles REFRESH_TOKEN_EXPIRED error_code"""

    def setup_method(self):
        """Setup API instance with mocked dependencies"""
        with patch('resources.lib.api.default_request_headers'), \
             patch('resources.lib.globals.G'):
            self.api = API()
            self.api.account_data = AccountData({
                'refresh_token': 'test_refresh_token',
                'token_type': 'Bearer',
                'access_token': 'test_access_token'
            })

    def test_create_session_triggers_device_flow_on_expired_refresh_token(self):
        """Test that create_session falls back to device flow when refresh token expires"""
        # Mock _handle_refresh_flow to raise LoginError with REFRESH_TOKEN_EXPIRED
        refresh_error = LoginError("Refresh token expired", error_code="REFRESH_TOKEN_EXPIRED")

        # Mock _handle_login_flow to succeed
        mock_login_flow = Mock()

        with patch.object(self.api, '_handle_refresh_flow', side_effect=refresh_error), \
             patch.object(self.api, '_handle_login_flow', mock_login_flow), \
             patch('xbmcgui.Dialog') as mock_dialog, \
             patch.object(self.api.account_data, 'delete_storage'):

            # Call create_session with action="refresh"
            self.api.create_session(action="refresh")

            # Verify dialog was shown
            mock_dialog.return_value.ok.assert_called_once()

            # Verify account data was deleted
            self.api.account_data.delete_storage.assert_called_once()

            # Verify _handle_login_flow was called (device flow)
            mock_login_flow.assert_called_once()

    def test_create_session_reraises_other_login_errors(self):
        """Test that create_session re-raises LoginError without REFRESH_TOKEN_EXPIRED"""
        # Mock _handle_refresh_flow to raise LoginError WITHOUT error_code
        refresh_error = LoginError("Network error")

        with patch.object(self.api, '_handle_refresh_flow', side_effect=refresh_error):

            # Should re-raise the LoginError
            with pytest.raises(LoginError) as exc_info:
                self.api.create_session(action="refresh")

            # Verify it's the same error
            assert str(exc_info.value) == "Network error"
            assert exc_info.value.error_code is None
