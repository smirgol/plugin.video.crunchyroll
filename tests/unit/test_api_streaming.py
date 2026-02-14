import json
from unittest.mock import Mock, patch

from resources.lib.api import API
from resources.lib.model import AccountData
from tests.fixtures.api_responses import STREAM_RESPONSE


class TestAPIStreamingUnit:
    """Unit Tests for Streaming API methods (mocked HTTP)"""

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

    def test_get_stream_urls(self):
        """Test stream URL retrieval"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = STREAM_RESPONSE
        mock_response.text = json.dumps(STREAM_RESPONSE)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response):

            bucket = self.api.account_data.cms.bucket
            episode_id = "GRVN1234X"

            result = self.api.make_request(
                method="GET",
                url=self.api.STREAMS_ENDPOINT.format(bucket, episode_id)
            )

            assert "streams" in result
            assert "adaptive_hls" in result["streams"]
            assert result["token"] == "mock_stream_token_abc123"

    def test_subtitle_parsing(self):
        """Test subtitle track parsing from stream response"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = STREAM_RESPONSE
        mock_response.text = json.dumps(STREAM_RESPONSE)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response):

            bucket = self.api.account_data.cms.bucket
            episode_id = "GRVN1234X"

            result = self.api.make_request(
                method="GET",
                url=self.api.STREAMS_ENDPOINT.format(bucket, episode_id)
            )

            assert "subtitles" in result
            assert "en-US" in result["subtitles"]
            assert "de-DE" in result["subtitles"]
            assert result["subtitles"]["en-US"]["format"] == "ass"

    def test_stream_audio_locale(self):
        """Test audio locale in stream response"""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = STREAM_RESPONSE
        mock_response.text = json.dumps(STREAM_RESPONSE)
        mock_response.headers = {"Content-Type": "application/json"}

        with patch.object(self.api, 'is_token_valid', return_value=True), \
             patch.object(self.api.http, 'request', return_value=mock_response):

            bucket = self.api.account_data.cms.bucket
            episode_id = "GRVN1234X"

            result = self.api.make_request(
                method="GET",
                url=self.api.STREAMS_ENDPOINT.format(bucket, episode_id),
                params={"audio_locale": "ja-JP"}
            )

            assert result["audio_locale"] == "ja-JP"
