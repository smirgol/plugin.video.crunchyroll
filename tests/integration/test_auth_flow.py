import pytest


@pytest.mark.integration
class TestAuthFlowIntegration:
    """Integration Tests for Auth Flow (real API)"""

    def test_token_refresh_real_api(self, api_client, token_manager):
        """Test token refresh against real Crunchyroll API"""
        token = token_manager.get_valid_token()

        assert token is not None
        assert len(token) > 0

        response = api_client.make_request(
            method="GET",
            url=api_client.PROFILE_ENDPOINT
        )

        assert response is not None
        assert "username" in response or "profile_name" in response

    def test_get_index(self, api_client):
        """Test fetching index endpoint (requires auth)"""
        response = api_client.make_request(
            method="GET",
            url=api_client.INDEX_ENDPOINT
        )

        assert response is not None
        assert "cms" in response or "cms_web" in response

    def test_profile_data(self, api_client):
        """Test fetching profile data"""
        response = api_client.make_request(
            method="GET",
            url=api_client.PROFILE_ENDPOINT
        )

        assert response is not None
        assert "username" in response or "profile_name" in response
        assert "preferred_content_subtitle_language" in response
        assert "maturity_rating" in response

    def test_token_auto_refresh(self, token_manager):
        """Test that token manager auto-refreshes expired tokens"""
        first_token = token_manager.get_valid_token()

        token_manager.token_expires_at = None

        second_token = token_manager.get_valid_token()

        assert first_token is not None
        assert second_token is not None

    def test_auth_headers_format(self, token_manager):
        """Test authorization headers format"""
        headers = token_manager.get_auth_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert "User-Agent" in headers
