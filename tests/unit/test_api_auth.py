from unittest.mock import Mock, patch

import pytest

from resources.lib.api import API
from resources.lib.model import LoginError, AccountData
from tests.fixtures.api_responses import (
    AUTH_TOKEN_RESPONSE,
    DEVICE_CODE_RESPONSE,
    ERROR_RESPONSE_401,
    ERROR_RESPONSE_500
)


class TestAPIAuthUnit:
    """Unit Tests for Authentication Logic (mocked HTTP)"""

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

    def test_token_refresh_success(self):
        """Test successful token refresh flow"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = AUTH_TOKEN_RESPONSE

        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', return_value=mock_response), \
             patch.object(self.api, '_finalize_session_from_tokens') as mock_finalize:

            self.api._handle_refresh_flow()

            mock_finalize.assert_called_once_with(AUTH_TOKEN_RESPONSE, action="refresh")

    def test_token_refresh_with_expired_refresh_token(self):
        """Test token refresh with expired refresh token raises LoginError"""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.json.return_value = ERROR_RESPONSE_401

        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', return_value=mock_response):

            with pytest.raises(LoginError):
                self.api._handle_refresh_flow()

    def test_device_code_generation(self):
        """Test device code generation"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = DEVICE_CODE_RESPONSE

        mock_scraper = Mock()
        mock_scraper.post.return_value = mock_response

        with patch.object(self.api, 'create_auth_scraper', return_value=mock_scraper):

            result = self.api.request_device_code()

            assert result["user_code"] == DEVICE_CODE_RESPONSE["user_code"]
            assert result["device_code"] == DEVICE_CODE_RESPONSE["device_code"]

    def test_device_token_polling_pending(self):
        """Test device token polling returns pending status"""
        with patch.object(self.api, '_process_device_token_response', return_value={"status": "pending"}), \
             patch.object(self.api, 'create_auth_scraper', return_value=Mock()):

            result = self.api.poll_device_token("mock_device_code")

            assert result["status"] == "pending"

    def test_device_token_polling_success(self):
        """Test successful device token polling"""
        with patch.object(self.api, '_process_device_token_response', return_value={"status": "success", "data": AUTH_TOKEN_RESPONSE}), \
             patch.object(self.api, 'create_auth_scraper', return_value=Mock()):

            result = self.api.poll_device_token("mock_device_code")

            assert result["status"] == "success"
            assert "data" in result

    def test_cloudscraper_fallback_to_requests(self):
        """Test that create_auth_scraper returns None when cloudscraper fails"""
        with patch('resources.lib.api.cloudscraper.create_scraper', side_effect=Exception("CloudScraper failed")):

            scraper = self.api.create_auth_scraper()

            assert scraper is None

    def test_server_error_handling(self):
        """Test handling of 500 server errors"""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.json.return_value = ERROR_RESPONSE_500

        with patch.object(self.api, 'create_auth_scraper', return_value=None), \
             patch.object(self.api.http, 'post', return_value=mock_response):

            with pytest.raises(LoginError):
                self.api._handle_refresh_flow()

    def test_authorization_header_device_auth(self):
        """Test correct authorization header for device auth"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = DEVICE_CODE_RESPONSE

        mock_scraper = Mock()
        mock_scraper.post.return_value = mock_response

        with patch.object(self.api, 'create_auth_scraper', return_value=mock_scraper):

            self.api.request_device_code()

            call_args = mock_scraper.post.call_args
            headers = call_args[1]["headers"]

            assert headers["Authorization"] == API.AUTHORIZATION_DEVICE
            assert headers["User-Agent"] == API.CRUNCHYROLL_UA_DEVICE
