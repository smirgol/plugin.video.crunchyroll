"""Unit tests for VideoStream ctx migration.

TDD: written before implementation.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import quote

import pytest


@pytest.fixture
def video_stream_ctx():
    """Provide a context that lets VideoStream exercise the ctx path."""
    from resources.lib.context import PluginContext

    mock_api = MagicMock()
    mock_api.STREAMS_ENDPOINT_DRM_ANDROID_TV = "https://www.crunchyroll.com/content/v2/cms/videos/{}/streams"
    mock_api.SKIP_EVENTS_ENDPOINT = "https://www.crunchyroll.com/skip-events/{}"
    mock_api.INTRO_V2_ENDPOINT = "https://www.crunchyroll.com/intro/{}"

    mock_account = MagicMock()
    mock_api.account_data = mock_account

    mock_args = MagicMock()
    mock_args.get_arg = MagicMock(return_value="episode-123")
    mock_args.addon = MagicMock()
    mock_args.addon.getSetting = MagicMock(return_value="true")
    mock_args.subtitle = "de-DE"
    mock_args.subtitle_fallback = "en-US"
    mock_args.addon_name = "Test"
    mock_args.argv = ["", "1", "?mode=videoplay", "resume:false"]

    mock_monitor = MagicMock()

    return PluginContext(api=mock_api, args=mock_args, monitor=mock_monitor)


class TestVideoStreamInit:
    def test_can_be_constructed_with_ctx(self, video_stream_ctx):
        from resources.lib.videostream import VideoStream

        stream = VideoStream(video_stream_ctx)
        assert stream._ctx is video_stream_ctx

    def test_requires_ctx(self):
        from resources.lib.videostream import VideoStream

        with pytest.raises(TypeError):
            VideoStream()


class TestSubtitleCacheReadiness:
    @pytest.fixture
    def subtitle_cache(self, video_stream_ctx, tmp_path):
        from resources.lib.videostream import VideoStream

        stream = VideoStream(video_stream_ctx)
        video_stream_ctx.api.make_request.return_value = {"data": "[Script Info]\nTitle: subtitles\n"}
        with patch.object(stream, "get_cache_path", return_value=str(tmp_path) + "/"), patch.object(
            stream, "get_cache_file_name", return_value="de-DE.de.ass"
        ), patch("resources.lib.videostream.xbmcvfs.translatePath", side_effect=lambda path: path), patch(
            "resources.lib.videostream.xbmcvfs.mkdirs", side_effect=lambda path: Path(path).mkdir(exist_ok=True)
        ), patch("resources.lib.videostream.xbmcvfs.exists", side_effect=lambda path: Path(path).exists()):
            yield stream, tmp_path / "episode-123" / "de-DE.de.ass"

    def test_returns_special_url_after_caching_subtitle(self, subtitle_cache):
        stream, cache_file = subtitle_cache

        result = stream._get_subtitle_from_cache("https://example.com/sub.ass", "de-DE", "ass")

        assert (
            result == "special://userdata/addon_data/plugin.video.crunchyroll/cache_subtitles/episode-123/de-DE.de.ass"
        )
        assert cache_file.read_text(encoding="utf-8") == stream._ctx.api.make_request.return_value["data"]

    def test_final_file_is_not_visible_until_write_is_complete(self, subtitle_cache):
        import os

        stream, cache_file = subtitle_cache
        replace = os.replace

        def publish(source, target):
            assert not cache_file.exists()
            assert Path(source).read_text(encoding="utf-8") == stream._ctx.api.make_request.return_value["data"]
            replace(source, target)

        with patch("resources.lib.videostream.os.replace", side_effect=publish) as mock_replace:
            stream._get_subtitle_from_cache("https://example.com/sub.ass", "de-DE", "ass")

        mock_replace.assert_called_once()
        assert list(cache_file.parent.iterdir()) == [cache_file]

    def test_failed_publish_does_not_leave_partial_cache_files(self, subtitle_cache):
        from resources.lib.models.exceptions import CrunchyrollError

        stream, cache_file = subtitle_cache

        with patch("resources.lib.videostream.os.replace", side_effect=OSError("cache write failed")):
            with pytest.raises(CrunchyrollError, match="Failed to cache subtitle"):
                stream._get_subtitle_from_cache("https://example.com/sub.ass", "de-DE", "ass")

        assert list(cache_file.parent.iterdir()) == []


class TestVideoStreamReadsArgsFromCtx:
    @patch("resources.lib.videostream.asyncio")
    def test_get_player_stream_data_uses_ctx_args_stream_id(self, mock_asyncio, video_stream_ctx):
        from resources.lib.videostream import VideoStream

        # minimal async result so the method can finish
        mock_asyncio.run.return_value = {
            "stream_data": {
                "url": "https://example.com/stream.mpd",
                "subtitles": [],
                "playheads": [],
                "token": "token123",
            }
        }

        stream = VideoStream(video_stream_ctx)
        stream.get_player_stream_data()

        video_stream_ctx.args.get_arg.assert_called_with("stream_id")


def _playback_response(key):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return copy.deepcopy(json.load(f)[key]["response"])


def _stream_args(soft_subtitles, subtitle="de-DE", subtitle_fallback="en-US"):
    settings = {"soft_subtitles": soft_subtitles}
    return SimpleNamespace(
        addon=SimpleNamespace(
            getSetting=lambda key: settings.get(key, ""),
            getLocalizedString=lambda string_id: f"string-{string_id}",
        ),
        addon_name="Test",
        argv=["", "1", "?mode=videoplay", "resume:false"],
        get_arg=lambda key, default=None: default,
        subtitle=subtitle,
        subtitle_fallback=subtitle_fallback,
    )


class TestGetStreamUrlFromApiDataV2:
    """Stream URL selection from playback/v2 data.

    Fixture URLs are www.crunchyroll.com manifests, so they pass the Cloudflare proxy. The proxy is
    patched to prefix the URL, making the selected manifest observable.
    """

    @pytest.fixture(autouse=True)
    def _proxy_and_gui(self):
        proxy = MagicMock()
        proxy.get_proxied_url.side_effect = lambda url: f"proxied:{url}"
        with patch("resources.lib.videostream.get_cloudflare_proxy", return_value=proxy), patch(
            "resources.lib.videostream.xbmcgui"
        ) as gui, patch("resources.lib.videostream.xbmcplugin") as plugin:
            self.gui = gui
            self.plugin = plugin
            yield

    @staticmethod
    def _select(api_data, args):
        from resources.lib.videostream import VideoStream

        return VideoStream._get_stream_url_from_api_data_v2(api_data, api=MagicMock(), args=args)

    def _assert_no_error_dialog(self):
        self.gui.Dialog.return_value.ok.assert_not_called()
        self.plugin.setResolvedUrl.assert_not_called()

    def test_soft_subtitles_returns_clean_manifest(self):
        api_data = _playback_response("playback_ja")

        url = self._select(api_data, _stream_args("true"))

        assert url == f"proxied:{api_data['url']}"

    def test_hard_subs_dub_selects_dub_language_hard_sub(self):
        # dub hard sub only carries signs/songs (Kodi check 2026-10-04); selection deliberately unchanged
        api_data = _playback_response("playback_de")

        url = self._select(api_data, _stream_args("false", subtitle="de-DE"))

        assert url == f"proxied:{api_data['hardSubs']['de-DE']['url']}"

    def test_hard_subs_original_selects_primary_subtitle(self):
        api_data = _playback_response("playback_ja")

        url = self._select(api_data, _stream_args("false", subtitle="de-DE", subtitle_fallback="en-US"))

        assert url == f"proxied:{api_data['hardSubs']['de-DE']['url']}"

    def test_hard_subs_original_falls_back_to_fallback_subtitle(self):
        api_data = _playback_response("playback_ja")

        url = self._select(api_data, _stream_args("false", subtitle="xx-XX", subtitle_fallback="en-US"))

        assert url == f"proxied:{api_data['hardSubs']['en-US']['url']}"

    def test_hard_subs_without_matching_language_returns_clean_manifest(self):
        api_data = _playback_response("playback_ja")

        url = self._select(api_data, _stream_args("false", subtitle="xx-XX", subtitle_fallback="yy-YY"))

        assert url == f"proxied:{api_data['url']}"

    def test_hard_subs_without_fallback_setting_returns_clean_manifest(self):
        api_data = _playback_response("playback_ja")

        url = self._select(api_data, _stream_args("false", subtitle="xx-XX", subtitle_fallback=None))

        assert url == f"proxied:{api_data['url']}"

    def test_missing_hard_subs_returns_clean_manifest(self):
        api_data = _playback_response("playback_ja")
        del api_data["hardSubs"]

        url = self._select(api_data, _stream_args("false"))

        assert url == f"proxied:{api_data['url']}"
        self._assert_no_error_dialog()

    def test_null_hard_subs_returns_clean_manifest(self):
        api_data = _playback_response("playback_ja")
        api_data["hardSubs"] = None

        url = self._select(api_data, _stream_args("false"))

        assert url == f"proxied:{api_data['url']}"
        self._assert_no_error_dialog()

    def test_proxy_log_line_hides_manifest_query_but_url_is_unchanged(self):
        manifest_url = "https://www.crunchyroll.com/evs/x/manifest.mpd?playbackGuid=secret123"
        proxy = MagicMock()
        proxy.get_proxied_url.side_effect = lambda url: "http://127.0.0.1:1/proxy?url=" + quote(url, safe="")

        with patch("resources.lib.videostream.get_cloudflare_proxy", return_value=proxy), patch(
            "resources.lib.videostream.crunchy_log"
        ) as mock_log:
            url = self._select({"url": manifest_url}, _stream_args("true"))

        proxy.get_proxied_url.assert_called_once_with(manifest_url)
        assert url == "http://127.0.0.1:1/proxy?url=" + quote(manifest_url, safe="")
        assert "secret123" in url
        lines = [str(c.args[0]) for c in mock_log.call_args_list if "Proxying manifest URL" in str(c.args[0])]
        assert len(lines) == 1, f"expected one proxy log line in {mock_log.call_args_list}"
        assert "secret123" not in lines[0]
