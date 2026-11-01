"""Unit tests for VideoStream ctx migration.

TDD: written before implementation.
"""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch
from urllib.parse import quote

import pytest
import requests


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


SIGNED_URL = "https://cdn.example.com/x/sub.ass?t=exp=1~acl=/x~hmac=abc"
PLAIN_URL = "https://www.crunchyroll.com/x/sub.ass"
CACHE_URL_PREFIX = "special://userdata/addon_data/plugin.video.crunchyroll/cache_subtitles/episode-123/"


def _track(url, language, subtitle_format):
    return {"url": url, "language": language, "format": subtitle_format}


def _tracks_api_data():
    return {
        "subtitles": {
            "fr-FR": _track("https://example.com/sub-fr.ass", "fr-FR", "ass"),
            "en-US": _track("https://example.com/sub-en.ass", "en-US", "ass"),
            "de-DE": _track("https://example.com/sub-de.ass", "de-DE", "ass"),
        },
        "captions": {
            "en-US": _track("https://example.com/cc-en.vtt", "en-US", "vtt"),
            "de-DE": _track("https://example.com/cc-de.vtt", "de-DE", "vtt"),
        },
    }


def _text_response(body: bytes, status_code: int = 200) -> requests.Response:
    """A real response as the CDN sends it: no charset, so requests would assume iso8859-1."""
    response = requests.Response()
    response.status_code = status_code
    response.reason = "Forbidden" if status_code == 403 else "OK"
    response.url = SIGNED_URL
    response.encoding = "ISO-8859-1"
    response._content = body
    return response


def _http_error_on_status():
    response = MagicMock()
    response.raise_for_status.side_effect = requests.HTTPError(f"403 Client Error: Forbidden for url: {SIGNED_URL}")
    return {"return_value": response}


def _connection_error_on_get():
    return {"side_effect": requests.ConnectionError(f"Max retries exceeded with url: {SIGNED_URL}")}


@pytest.fixture
def captured_logs():
    """Collect everything logged, so a leak through any logger is detected. Returns a callable giving the text."""
    import xbmc

    from resources.lib.utils.logging import crunchy_log

    with patch.object(xbmc, "log") as xbmc_log, patch(
        "resources.lib.videostream.crunchy_log", wraps=crunchy_log
    ) as stream_log:
        yield lambda: "\n".join(str(c) for c in xbmc_log.call_args_list + stream_log.call_args_list)


@pytest.fixture
def track_stream(video_stream_ctx):
    """A VideoStream whose per-track caching is a mock, to observe which tracks are selected."""
    from resources.lib.videostream import VideoStream

    stream = VideoStream(video_stream_ctx)
    with patch.object(stream, "_get_subtitle_from_cache") as from_cache:
        from_cache.side_effect = lambda url, *_args, **_kwargs: f"cached:{url}"
        yield stream, from_cache


@pytest.fixture
def cached_stream(video_stream_ctx, tmp_path):
    """A VideoStream that caches into tmp_path. API requests answer with a body derived from the url."""
    from resources.lib.videostream import VideoStream

    stream = VideoStream(video_stream_ctx)
    video_stream_ctx.api.make_request.side_effect = lambda method, url: {"data": f"body of {url}"}
    with patch.object(stream, "get_cache_path", return_value=str(tmp_path) + "/"), patch(
        "resources.lib.videostream.xbmcvfs.translatePath", side_effect=lambda path: path
    ), patch(
        "resources.lib.videostream.xbmcvfs.mkdirs", side_effect=lambda path: Path(path).mkdir(exist_ok=True)
    ), patch("resources.lib.videostream.xbmcvfs.exists", side_effect=lambda path: Path(path).exists()), patch(
        "resources.lib.videostream.xbmcvfs.makeLegalFilename", side_effect=lambda name: name
    ):
        yield stream, tmp_path / "episode-123"


class TestSubtitleTrackSelection:
    def test_order_is_primary_then_fallback_with_subtitles_before_captions(self, track_stream):
        stream, from_cache = track_stream

        result = stream._get_subtitles_from_api_data(_tracks_api_data())

        urls = [c.args[0] for c in from_cache.call_args_list]
        assert urls == [
            "https://example.com/sub-de.ass",
            "https://example.com/cc-de.vtt",
            "https://example.com/sub-en.ass",
            "https://example.com/cc-en.vtt",
        ]
        assert result == [f"cached:{url}" for url in urls]

    def test_tracks_are_requested_with_their_caption_flag(self, track_stream):
        stream, from_cache = track_stream

        stream._get_subtitles_from_api_data(_tracks_api_data())

        assert from_cache.call_args_list == [
            call("https://example.com/sub-de.ass", "de-DE", "ass", is_caption=False),
            call("https://example.com/cc-de.vtt", "de-DE", "vtt", is_caption=True),
            call("https://example.com/sub-en.ass", "en-US", "ass", is_caption=False),
            call("https://example.com/cc-en.vtt", "en-US", "vtt", is_caption=True),
        ]

    def test_language_configured_as_primary_and_fallback_is_processed_once(self, track_stream):
        stream, from_cache = track_stream
        stream._ctx.args.subtitle_fallback = "de-DE"

        stream._get_subtitles_from_api_data(_tracks_api_data())

        urls = [c.args[0] for c in from_cache.call_args_list]
        assert urls == ["https://example.com/sub-de.ass", "https://example.com/cc-de.vtt"]

    @pytest.mark.parametrize("captions", [{"captions": None}, {}], ids=["null", "missing"])
    def test_absent_captions_are_tolerated(self, track_stream, captions):
        stream, _ = track_stream
        api_data = {"subtitles": _tracks_api_data()["subtitles"], **captions}

        result = stream._get_subtitles_from_api_data(api_data)

        assert result == ["cached:https://example.com/sub-de.ass", "cached:https://example.com/sub-en.ass"]

    def test_api_data_is_not_mutated(self, track_stream):
        stream, _ = track_stream
        api_data = _tracks_api_data()
        expected = copy.deepcopy(api_data)

        stream._get_subtitles_from_api_data(api_data)

        assert api_data == expected

    @pytest.mark.parametrize(
        "caption",
        [
            {"url": "https://example.com/cc.vtt", "format": "vtt"},
            {"url": "https://example.com/cc.vtt", "format": "vtt", "language": None},
        ],
        ids=["missing", "null"],
    )
    def test_caption_without_language_does_not_yield_none_name(self, cached_stream, caption):
        stream, cache_dir = cached_stream

        result = stream._get_subtitles_from_api_data({"subtitles": {}, "captions": {"de-DE": caption}})

        written = [path.name for path in cache_dir.iterdir()] if cache_dir.exists() else []
        assert not [name for name in list(result or []) + written if "None" in name]


class TestFailedSubtitleTracks:
    def test_failed_track_does_not_stop_remaining_tracks(self, track_stream):
        from resources.lib.models.exceptions import CrunchyrollError

        stream, from_cache = track_stream
        from_cache.side_effect = [CrunchyrollError("boom"), "cached-cc-de", "cached-sub-en", "cached-cc-en"]

        result = stream._get_subtitles_from_api_data(_tracks_api_data())

        assert result == ["cached-cc-de", "cached-sub-en", "cached-cc-en"]

    def test_failed_track_is_logged(self, track_stream, captured_logs):
        from resources.lib.models.exceptions import CrunchyrollError

        stream, from_cache = track_stream
        from_cache.side_effect = [CrunchyrollError("boom"), "cached-cc-de", "cached-sub-en", "cached-cc-en"]

        stream._get_subtitles_from_api_data(_tracks_api_data())

        assert "boom" in captured_logs()

    def test_raises_after_trying_every_track_if_all_failed(self, track_stream):
        from resources.lib.models.exceptions import CrunchyrollError

        stream, from_cache = track_stream
        from_cache.side_effect = CrunchyrollError("boom")

        with pytest.raises(CrunchyrollError):
            stream._get_subtitles_from_api_data(_tracks_api_data())

        assert from_cache.call_count == 4

    def test_raises_if_a_track_failed_and_the_others_returned_none(self, track_stream):
        from resources.lib.models.exceptions import CrunchyrollError

        stream, from_cache = track_stream
        from_cache.side_effect = [None, CrunchyrollError("boom"), None, None]

        with pytest.raises(CrunchyrollError):
            stream._get_subtitles_from_api_data(_tracks_api_data())

        assert from_cache.call_count == 4

    def test_none_result_does_not_stop_remaining_tracks(self, track_stream):
        stream, from_cache = track_stream
        from_cache.side_effect = [None, "cached-cc-de", None, "cached-cc-en"]

        result = stream._get_subtitles_from_api_data(_tracks_api_data())

        assert result == ["cached-cc-de", "cached-cc-en"]

    def test_only_none_results_do_not_raise(self, track_stream):
        stream, from_cache = track_stream
        from_cache.side_effect = lambda *_args, **_kwargs: None

        result = stream._get_subtitles_from_api_data(_tracks_api_data())

        assert result == []
        assert from_cache.call_count == 4


class TestCaptionFileNames:
    @pytest.fixture(autouse=True)
    def _legal_filename(self):
        with patch("resources.lib.videostream.xbmcvfs.makeLegalFilename", side_effect=lambda name: name):
            yield

    def test_subtitle_file_name_without_flag(self):
        from resources.lib.videostream import VideoStream

        assert VideoStream.get_cache_file_name("de-DE", "ass") == "de.ass"

    def test_subtitle_file_name_with_explicit_flag(self):
        from resources.lib.videostream import VideoStream

        assert VideoStream.get_cache_file_name("de-DE", "ass", is_caption=False) == "de.ass"

    def test_caption_file_name(self):
        from resources.lib.videostream import VideoStream

        assert VideoStream.get_cache_file_name("de-DE", "vtt", is_caption=True) == "de.[cc].vtt"

    @pytest.mark.parametrize(
        "language, subtitle_format, is_caption, expected",
        [
            ("de-DE", "ass", False, "de.ass"),
            ("de-DE", "vtt", True, "de.[cc].vtt"),
            ("en-US", "ass", False, "US.en.ass"),
            ("en-US", "vtt", True, "US.en.[cc].vtt"),
            ("pt-BR", "ass", False, "BR.pt.ass"),
            ("pt-PT", "ass", False, "pt.ass"),
            ("es-419", "ass", False, "419.es.ass"),
            ("es-ES", "ass", False, "es.ass"),
            ("ja", "ass", False, "ja.ass"),
        ],
    )
    def test_cache_file_name_format(self, language, subtitle_format, is_caption, expected):
        from resources.lib.videostream import VideoStream

        assert VideoStream.get_cache_file_name(language, subtitle_format, is_caption=is_caption) == expected

    def test_regional_variants_of_a_language_get_different_names(self):
        from resources.lib.videostream import VideoStream

        assert VideoStream.get_cache_file_name("pt-BR", "ass") != VideoStream.get_cache_file_name("pt-PT", "ass")

    def test_subtitle_and_caption_of_same_language_get_different_names(self):
        from resources.lib.videostream import VideoStream

        subtitle_name = VideoStream.get_cache_file_name("de-DE", "vtt", is_caption=False)
        caption_name = VideoStream.get_cache_file_name("de-DE", "vtt", is_caption=True)

        assert subtitle_name != caption_name

    def test_get_subtitle_from_cache_without_flag_uses_subtitle_name(self, cached_stream):
        stream, cache_dir = cached_stream

        result = stream._get_subtitle_from_cache(PLAIN_URL, "de-DE", "ass")

        assert result == CACHE_URL_PREFIX + "de.ass"
        assert (cache_dir / "de.ass").is_file()

    def test_get_subtitle_from_cache_with_flag_uses_caption_name(self, cached_stream):
        stream, cache_dir = cached_stream

        result = stream._get_subtitle_from_cache(PLAIN_URL, "de-DE", "vtt", is_caption=True)

        assert result == CACHE_URL_PREFIX + "de.[cc].vtt"
        assert (cache_dir / "de.[cc].vtt").is_file()

    def test_cache_subtitle_without_flag_uses_subtitle_name(self, cached_stream):
        stream, cache_dir = cached_stream

        assert stream._cache_subtitle(PLAIN_URL, "de-DE", "ass") is True

        assert (cache_dir / "de.ass").is_file()

    def test_cache_subtitle_with_flag_uses_caption_name(self, cached_stream):
        stream, cache_dir = cached_stream

        assert stream._cache_subtitle(PLAIN_URL, "de-DE", "vtt", is_caption=True) is True

        assert (cache_dir / "de.[cc].vtt").is_file()

    def test_subtitle_and_caption_of_same_language_and_format_are_both_downloaded(self, cached_stream):
        stream, cache_dir = cached_stream
        api_data = {
            "subtitles": {"de-DE": _track("https://example.com/sub.vtt", "de-DE", "vtt")},
            "captions": {"de-DE": _track("https://example.com/cc.vtt", "de-DE", "vtt")},
        }

        result = stream._get_subtitles_from_api_data(api_data)

        assert result == [CACHE_URL_PREFIX + "de.vtt", CACHE_URL_PREFIX + "de.[cc].vtt"]
        assert (cache_dir / "de.vtt").read_text(encoding="utf-8") == "body of https://example.com/sub.vtt"
        assert (cache_dir / "de.[cc].vtt").read_text(encoding="utf-8") == "body of https://example.com/cc.vtt"


class TestFetchSubtitle:
    @pytest.fixture
    def stream(self, video_stream_ctx):
        from resources.lib.videostream import VideoStream

        return VideoStream(video_stream_ctx)

    def test_signed_url_is_downloaded_directly(self, stream):
        with patch("resources.lib.videostream.requests.get", return_value=_text_response(b"subtitle")) as mock_get:
            result = stream._fetch_subtitle(SIGNED_URL, "de-DE")

        mock_get.assert_called_once_with(SIGNED_URL, timeout=30)
        stream._ctx.api.make_request.assert_not_called()
        assert result == "subtitle"

    def test_signed_url_body_is_decoded_as_utf8(self, stream):
        body = "Übersetzung – 日本語"

        with patch("resources.lib.videostream.requests.get", return_value=_text_response(body.encode("utf-8"))):
            result = stream._fetch_subtitle(SIGNED_URL, "de-DE")

        assert result == body

    def test_signed_url_http_error_raises_crunchyroll_error(self, stream):
        from resources.lib.models.exceptions import CrunchyrollError

        with patch("resources.lib.videostream.requests.get", return_value=_text_response(b"denied", 403)):
            with pytest.raises(CrunchyrollError):
                stream._fetch_subtitle(SIGNED_URL, "de-DE")

    def test_other_url_goes_through_the_api(self, stream):
        stream._ctx.api.make_request.return_value = {"data": "subtitle"}

        with patch("resources.lib.videostream.requests.get") as mock_get:
            result = stream._fetch_subtitle(PLAIN_URL, "de-DE")

        stream._ctx.api.make_request.assert_called_once_with(method="GET", url=PLAIN_URL)
        mock_get.assert_not_called()
        assert result == "subtitle"

    def test_other_url_without_data_returns_none(self, stream):
        stream._ctx.api.make_request.return_value = {}

        assert stream._fetch_subtitle(PLAIN_URL, "de-DE") is None


class TestSignedUrlsStayOutOfLogsAndExceptions:
    @pytest.fixture
    def stream(self, cached_stream):
        return cached_stream[0]

    @pytest.mark.parametrize(
        "failure, expected_in_log",
        [(_http_error_on_status, "403 Client Error"), (_connection_error_on_get, "Max retries exceeded")],
        ids=["http_error", "connection_error"],
    )
    def test_failed_download_does_not_expose_signature(self, stream, captured_logs, failure, expected_in_log):
        from resources.lib.models.exceptions import CrunchyrollError

        with patch("resources.lib.videostream.requests.get", **failure()):
            with pytest.raises(CrunchyrollError) as raised:
                stream._fetch_subtitle(SIGNED_URL, "de-DE")

        assert "hmac=" not in str(raised.value)
        assert "hmac=" not in captured_logs()
        # the error itself stays diagnosable
        assert expected_in_log in captured_logs()

    def test_all_tracks_failing_does_not_expose_signature(self, stream, captured_logs):
        from resources.lib.models.exceptions import CrunchyrollError

        api_data = {
            "subtitles": {"de-DE": _track(SIGNED_URL, "de-DE", "ass")},
            "captions": {"de-DE": _track(SIGNED_URL, "de-DE", "vtt")},
        }

        with patch("resources.lib.videostream.requests.get", **_http_error_on_status()):
            with pytest.raises(CrunchyrollError) as raised:
                stream._get_subtitles_from_api_data(api_data)

        assert "hmac=" not in str(raised.value)
        assert "hmac=" not in captured_logs()

    def test_failed_track_shows_no_notification(self, stream, captured_logs):
        api_data = {
            "subtitles": {"de-DE": _track(SIGNED_URL, "de-DE", "ass")},
            "captions": {"de-DE": _track(PLAIN_URL, "de-DE", "vtt")},
        }

        with patch("resources.lib.videostream.requests.get", **_http_error_on_status()), patch(
            "resources.lib.utils.logging.xbmcgui"
        ) as gui:
            stream._get_subtitles_from_api_data(api_data)

        gui.Dialog.return_value.notification.assert_not_called()
