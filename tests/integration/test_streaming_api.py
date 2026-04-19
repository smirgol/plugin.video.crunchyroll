import pytest


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.streaming
class TestStreamingAPIIntegration:
    """Integration Tests for Streaming API (real API)

    WARNING: Use sparingly! Stream counter can block requests.
    - Max 2-3 tests total
    - Always use same test episode
    - Always use stream_cleanup fixture
    - clean_all_streams_before_suite runs once before all tests
    """

    def test_get_stream_urls(
        self,
        api_client,
        stream_cleanup,
        test_episode_id,
        clean_all_streams_before_suite
    ):
        """Test stream URL retrieval and cleanup"""
        bucket = "/crunchyroll"

        response = api_client.make_request(
            url=api_client.STREAMS_ENDPOINT.format(bucket, test_episode_id),
            method="GET"
        )

        if response.status_code != 200:
            pytest.skip(f"Stream request failed: {response.status_code}")

        data = response.json()

        assert "streams" in data
        assert "adaptive_hls" in data["streams"]

        token = data.get("token")
        if token:
            stream_cleanup(token, test_episode_id)

        assert token is not None

        hls_streams = data["streams"]["adaptive_hls"]
        assert len(hls_streams) > 0

        first_stream = list(hls_streams.values())[0]
        assert "url" in first_stream
        assert first_stream["url"].startswith("http")

    def test_subtitle_tracks(
        self,
        api_client,
        stream_cleanup,
        test_episode_id,
        clean_all_streams_before_suite
    ):
        """Test subtitle track parsing"""
        bucket = "/crunchyroll"

        response = api_client.make_request(
            url=api_client.STREAMS_ENDPOINT.format(bucket, test_episode_id),
            method="GET"
        )

        if response.status_code != 200:
            pytest.skip(f"Stream request failed: {response.status_code}")

        data = response.json()

        token = data.get("token")
        if token:
            stream_cleanup(token, test_episode_id)

        assert "subtitles" in data

        subtitles = data["subtitles"]
        if len(subtitles) > 0:
            first_sub_locale = list(subtitles.keys())[0]
            first_sub = subtitles[first_sub_locale]

            assert "url" in first_sub
            assert "locale" in first_sub
            assert first_sub["url"].startswith("http")
            assert first_sub["locale"] == first_sub_locale

    def test_verify_no_active_streams_after_cleanup(
        self,
        api_client,
        clean_all_streams_before_suite
    ):
        """Verify stream cleanup works by checking active streams

        This test should run LAST to verify cleanup worked.
        """
        response = api_client.make_request(
            url=api_client.STREAMS_ENDPOINT_GET_ACTIVE_STREAMS,
            method="GET"
        )

        if response.status_code == 200:
            data = response.json()
            active_streams = data.get("data", [])

            assert len(active_streams) == 0, (
                f"Found {len(active_streams)} active streams after cleanup! "
                f"Stream cleanup may have failed."
            )
