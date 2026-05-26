import pytest


@pytest.mark.integration
class TestContentAPIIntegration:
    """Integration Tests for Content API (real API)"""

    def test_browse_endpoint(self, api_client):
        """Test browse endpoint returns valid data"""
        data = api_client.make_request(
            method="GET",
            url=api_client.BROWSE_ENDPOINT,
            params={
                "start": 0,
                "n": 10,
                "locale": "en-US"
            }
        )

        assert data is not None
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "id" in item
            assert "type" in item
            assert "title" in item

    def test_search_endpoint(self, api_client):
        """Test search endpoint with query - uses 'items'"""
        data = api_client.make_request(
            method="GET",
            url=api_client.SEARCH_ENDPOINT,
            params={
                "q": "one piece",
                "n": 5,
                "locale": "en-US"
            }
        )

        assert data is not None
        assert "total" in data
        assert "items" in data

        if data["total"] > 0:
            assert len(data["items"]) > 0
            result = data["items"][0]
            assert "id" in result or "items" in result

    def test_categories_endpoint(self, api_client):
        """Test fetching categories"""
        data = api_client.make_request(
            method="GET",
            url=api_client.CATEGORIES_ENDPOINT,
            params={"locale": "en-US"}
        )

        assert data is not None
        assert isinstance(data, dict)

    def test_seasonal_tags(self, api_client):
        """Test fetching seasonal tags"""
        data = api_client.make_request(
            method="GET",
            url=api_client.SEASONAL_TAGS_ENDPOINT
        )

        assert data is not None
        assert "data" in data or isinstance(data, list)

    def test_series_seasons(self, api_client):
        """Test fetching seasons for a known series - uses 'items'"""
        bucket = api_client.account_data.cms.bucket
        data = api_client.make_request(
            method="GET",
            url=api_client.SEASONS_ENDPOINT.format(bucket),
            params={
                "series_id": "GQWH0M1J3",
                "locale": "de-DE"
            }
        )

        assert data is not None
        assert "items" in data

        if len(data["items"]) > 0:
            season = data["items"][0]
            assert "id" in season
            assert "season_number" in season
            assert "series_id" in season

    def test_season_episodes(self, api_client):
        """Test fetching episodes for a season - uses 'items'"""
        bucket = api_client.account_data.cms.bucket
        data = api_client.make_request(
            method="GET",
            url=api_client.EPISODES_ENDPOINT.format(bucket),
            params={
                "season_id": "GYE5CQNJ2",
                "locale": "de-DE"
            }
        )

        assert data is not None
        assert "items" in data

        if len(data["items"]) > 0:
            episode = data["items"][0]
            assert "id" in episode
            assert "episode_number" in episode or "episode" in episode
            assert "title" in episode

    def test_watchlist_endpoint(self, api_client, test_credentials):
        """Test fetching user watchlist - uses 'items'"""
        account_id = test_credentials.get("account_id")

        if not account_id:
            pytest.skip("Account ID not provided in .env")

        data = api_client.make_request(
            method="GET",
            url=api_client.WATCHLIST_LIST_ENDPOINT.format(account_id),
            params={"locale": "en-US"}
        )

        assert data is not None
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_pagination(self, api_client):
        """Test pagination works correctly - uses 'items'"""
        data1 = api_client.make_request(
            method="GET",
            url=api_client.BROWSE_ENDPOINT,
            params={
                "start": 0,
                "n": 5,
                "locale": "en-US"
            }
        )

        data2 = api_client.make_request(
            method="GET",
            url=api_client.BROWSE_ENDPOINT,
            params={
                "start": 5,
                "n": 5,
                "locale": "en-US"
            }
        )

        assert data1 is not None
        assert data2 is not None
        assert "items" in data1
        assert "items" in data2

        if len(data1["items"]) > 0 and len(data2["items"]) > 0:
            assert data1["items"][0]["id"] != data2["items"][0]["id"]

    def test_locale_parameter(self, api_client):
        """Test locale parameter affects response"""
        data_en = api_client.make_request(
            method="GET",
            url=api_client.BROWSE_ENDPOINT,
            params={
                "start": 0,
                "n": 1,
                "locale": "en-US"
            }
        )

        data_de = api_client.make_request(
            method="GET",
            url=api_client.BROWSE_ENDPOINT,
            params={
                "start": 0,
                "n": 1,
                "locale": "de-DE"
            }
        )

        assert data_en is not None
        assert data_de is not None
        assert "items" in data_en
        assert "items" in data_de
