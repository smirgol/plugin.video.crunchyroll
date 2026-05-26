import pytest

from resources.lib.model import CrunchyrollError


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.streaming
class TestStreamingAPIIntegration:
    """Integration Tests for Streaming API (real API)

    WARNING: Use sparingly! Stream counter can block requests.
    - Max 2-3 tests total
    - Always use same test episode
    - Always use stream_cleanup fixture
    - test_clear_all_active_streams runs first and resets stream slots
    """

    def test_clear_all_active_streams(self, api_client):
        """Clear all active stream slots before running streaming tests.

        Crunchyroll limits concurrent streams per account. Without cleanup,
        subsequent stream requests fail with 'Playback is Rejected'.
        Must run first in this class.
        """
        try:
            response = api_client.make_scraper_request(
                method="GET",
                url=api_client.STREAMS_ENDPOINT_GET_ACTIVE_STREAMS,
                auth_type="device"
            )
        except Exception as e:
            pytest.skip(f"Could not fetch active streams: {e}")

        items = response.get("items", [])

        for item in items:
            token = item.get("token")
            content_id = item.get("contentId") or item.get("episodeId") or item.get("id")
            if token and content_id:
                try:
                    api_client.make_request(
                        method="DELETE",
                        url=api_client.STREAMS_ENDPOINT_CLEAR_STREAM.format(content_id, token)
                    )
                except Exception as e:
                    print(f"Warning: Failed to clear stream {content_id}: {e}")

    def _get_stream_data(self, api_client, test_episode_id):
        url = api_client.STREAMS_ENDPOINT_DRM_ANDROID_TV.format(test_episode_id)
        try:
            return api_client.make_scraper_request(
                method="GET",
                url=url,
                auth_type="device",
                auto_refresh=True
            )
        except CrunchyrollError as e:
            pytest.skip(f"Stream request rejected by API (stream limit or unavailable): {e}")

    def test_get_stream_urls(
        self,
        api_client,
        stream_cleanup,
        test_episode_id
    ):
        """Test stream URL retrieval using the AndroidTV DRM endpoint"""
        data = self._get_stream_data(api_client, test_episode_id)

        token = data.get("token")
        if token:
            stream_cleanup(token, test_episode_id)

        assert "url" in data
        assert data["url"].startswith("http")
        assert token is not None

    def test_subtitle_tracks(
        self,
        api_client,
        stream_cleanup,
        test_episode_id
    ):
        """Test subtitle track availability in stream response"""
        data = self._get_stream_data(api_client, test_episode_id)

        token = data.get("token")
        if token:
            stream_cleanup(token, test_episode_id)

        assert "subtitles" in data

        subtitles = data["subtitles"]
        if subtitles:
            first_locale = list(subtitles.keys())[0]
            first_sub = subtitles[first_locale]
            assert "url" in first_sub
            assert first_sub["url"].startswith("http")
            assert "format" in first_sub

    def test_subtitle_file_download(
        self,
        api_client,
        stream_cleanup,
        test_episode_id
    ):
        """Test that subtitle files can be downloaded and get_json_from_response handles the content-type.

        This test catches regressions where the CDN changes the content-type of subtitle responses
        (e.g. from text/plain to application/octet-stream) causing get_json_from_response to fail.
        """
        data = self._get_stream_data(api_client, test_episode_id)

        token = data.get("token")
        if token:
            stream_cleanup(token, test_episode_id)

        subtitles = data.get("subtitles", {})
        if not subtitles:
            pytest.skip("No subtitles available for this episode")

        first_locale = list(subtitles.keys())[0]
        subtitle_url = subtitles[first_locale]["url"]

        result = api_client.make_unauthenticated_request(method="GET", url=subtitle_url)

        assert result is not None, "Subtitle download returned None - content-type likely not handled"
        assert "data" in result, f"Expected 'data' key in subtitle response, got: {list(result.keys())}"
        assert len(result["data"]) > 0