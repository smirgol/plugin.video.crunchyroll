"""Unit tests for VideoStream ctx migration.

TDD: written before implementation.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
