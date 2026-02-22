import json
from unittest.mock import Mock, patch

from resources.lib.api import API
from resources.lib.model import AccountData
from tests.fixtures.api_responses import (
    BROWSE_RESPONSE,
    SEASONS_RESPONSE,
    EPISODES_RESPONSE,
    SEARCH_RESPONSE,
    WATCHLIST_RESPONSE
)


class TestAPIContentUnit:
    """Unit Tests for Content API methods (mocked HTTP)"""

    def setup_method(self):
        """Setup API instance with mocked dependencies"""
        with patch('resources.lib.api.default_request_headers'), \
             patch('resources.lib.globals.G'):
            self.api = API()
            self.api.account_data = AccountData({
                'access_token': 'test_access_token',
                'refresh_token': 'test_refresh_token',
                'token_type': 'Bearer'
            })
            self.api.account_data.cms = Mock()
            self.api.account_data.cms.policy = "test_policy"
            self.api.account_data.cms.signature = "test_sig"
            self.api.account_data.cms.key_pair_id = "test_key"
            self.api.account_data.cms.bucket = "/DE/M3/crunchyroll"

    def test_browse_request(self):
        """Test browse endpoint request - uses 'items' not 'data'"""
        browse_data = BROWSE_RESPONSE.copy()
        browse_data["items"] = browse_data.pop("data")

        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = browse_data
        mock_response.text = json.dumps(browse_data)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response):

            result = self.api.make_request(
                method="GET",
                url=self.api.BROWSE_ENDPOINT,
                params={"start": 0, "n": 20}
            )

            assert "items" in result
            assert result["total"] == 50
            assert len(result["items"]) == 1
            assert result["items"][0]["id"] == "GRVN8VK8R"

    def test_search_request(self):
        """Test search endpoint request - uses 'items' not 'data'"""
        search_data = SEARCH_RESPONSE.copy()
        search_data["items"] = search_data.pop("data")

        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = search_data
        mock_response.text = json.dumps(search_data)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response):

            result = self.api.make_request(
                method="GET",
                url=self.api.SEARCH_ENDPOINT,
                params={"q": "test anime", "n": 10}
            )

            assert "items" in result
            assert result["total"] == 5
            assert result["items"][0]["type"] == "series"

    def test_seasons_request(self):
        """Test seasons endpoint request - uses 'data'"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = SEASONS_RESPONSE
        mock_response.text = json.dumps(SEASONS_RESPONSE)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response):

            bucket = self.api.account_data.cms.bucket
            result = self.api.make_request(
                method="GET",
                url=self.api.SEASONS_ENDPOINT.format(bucket),
                params={"series_id": "GRVN8VK8R"}
            )

            assert "data" in result
            assert result["total"] == 2
            assert result["data"][0]["season_number"] == 1
            assert result["data"][1]["season_number"] == 2

    def test_episodes_request(self):
        """Test episodes endpoint request - uses 'data'"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = EPISODES_RESPONSE
        mock_response.text = json.dumps(EPISODES_RESPONSE)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response):

            bucket = self.api.account_data.cms.bucket
            result = self.api.make_request(
                method="GET",
                url=self.api.EPISODES_ENDPOINT.format(bucket),
                params={"season_id": "GRJ0X123Y"}
            )

            assert "data" in result
            assert result["total"] == 12
            assert result["data"][0]["episode_number"] == 1

    def test_watchlist_request(self):
        """Test watchlist endpoint request - uses 'data'"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = WATCHLIST_RESPONSE
        mock_response.text = json.dumps(WATCHLIST_RESPONSE)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response):

            account_id = "test_account_123"
            result = self.api.make_request(
                method="GET",
                url=self.api.WATCHLIST_LIST_ENDPOINT.format(account_id)
            )

            assert "data" in result
            assert result["total"] == 3
            assert result["data"][0]["is_favorite"] is True

    def test_cms_params_included(self):
        """Test that CMS params are included in requests"""
        browse_data = BROWSE_RESPONSE.copy()
        browse_data["items"] = browse_data.pop("data")

        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = browse_data
        mock_response.text = json.dumps(browse_data)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response) as mock_request:

            self.api.make_request(
                method="GET",
                url=self.api.BROWSE_ENDPOINT,
                params={"start": 0}
            )

            call_args = mock_request.call_args
            params = call_args[1].get("params", {})

            assert "Policy" in params
            assert params["Policy"] == "test_policy"

    def test_pagination_params(self):
        """Test pagination parameters in requests"""
        browse_data = BROWSE_RESPONSE.copy()
        browse_data["items"] = browse_data.pop("data")

        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = browse_data
        mock_response.text = json.dumps(browse_data)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response) as mock_request:

            self.api.make_request(
                method="GET",
                url=self.api.BROWSE_ENDPOINT,
                params={"start": 20, "n": 50}
            )

            call_args = mock_request.call_args
            params = call_args[1].get("params", {})

            assert params["start"] == 20
            assert params["n"] == 50

    def test_locale_params(self):
        """Test locale parameters in requests"""
        browse_data = BROWSE_RESPONSE.copy()
        browse_data["items"] = browse_data.pop("data")

        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = browse_data
        mock_response.text = json.dumps(browse_data)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response) as mock_request:

            self.api.make_request(
                method="GET",
                url=self.api.BROWSE_ENDPOINT,
                params={"locale": "de-DE"}
            )

            call_args = mock_request.call_args
            params = call_args[1].get("params", {})

            assert params["locale"] == "de-DE"
