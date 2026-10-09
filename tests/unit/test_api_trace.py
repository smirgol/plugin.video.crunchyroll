"""
Unit tests for API request/response tracing (resources/lib/utils/api_trace.py)

Covers parameter redaction, compact response summaries, the debug-setting gate
and the integration of the trace output into the API request methods.
"""

import json
import types
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from resources.lib.api import API
from resources.lib.http_utils import get_json_from_response
from resources.lib.models.account import AccountData
from resources.lib.models.exceptions import CrunchyrollError, LoginError
from resources.lib.utils.api_trace import is_trace_enabled, redact_params, redact_url, summarize_response

FIXTURES_FILE = Path(__file__).parent.parent / "fixtures" / "captured_responses.json"

ACCESS_TOKEN = "secret-access-token-xyz"
CMS_POLICY = "secret-policy-value"
CMS_SIGNATURE = "secret-signature-value"
CMS_KEY_PAIR_ID = "secret-key-pair-id"

CLEAR_STREAM_CONTENT_ID = "G50UMN15P"
CLEAR_STREAM_TOKEN = "secret-stream-token-abc123"

SIGNED_SUBTITLE_PATH = (
    "https://vod-fy-mod.crunchyrollcdn.com/static/majin/x/clean/subtitles/dede/20260925_155931_0d017218/subtitle.ass"
)
SIGNED_SUBTITLE_URL = SIGNED_SUBTITLE_PATH + "?t=exp=1791169290~acl=/static/majin/x/subtitle.ass~hmac=d510c9e2"


@pytest.fixture(scope="module")
def captured():
    with open(FIXTURES_FILE, encoding="utf-8") as f:
        return json.load(f)


def make_args(debug_logging: str) -> Mock:
    args = Mock()
    args.device_id = "test-device-id"
    args.addon_name = "TestCrunchyroll"
    args.addon.getLocalizedString.return_value = "localized"
    args.addon.getSetting.side_effect = lambda key: debug_logging if key == "debug_logging" else ""
    return args


def make_json_response(body: dict, status_code: int = 200) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 400
    response.headers = {"Content-Type": "application/json"}
    response.text = json.dumps(body)
    response.json.return_value = body
    return response


def make_api(debug_logging: str, args=None) -> API:
    with patch("resources.lib.api.default_request_headers"):
        api = API(args=args if args is not None else make_args(debug_logging))
    api.account_data = AccountData(
        {
            "access_token": ACCESS_TOKEN,
            "token_type": "Bearer",
            "refresh_token": "secret-refresh-token",
            "cms": {
                "bucket": "/de",
                "policy": CMS_POLICY,
                "signature": CMS_SIGNATURE,
                "key_pair_id": CMS_KEY_PAIR_ID,
            },
        }
    )
    return api


def logged_messages(mock_log: Mock) -> list:
    return [str(c.args[0]) if c.args else str(c.kwargs.get("message", "")) for c in mock_log.call_args_list]


class TestRedactParams:
    def test_none_returns_empty_dict(self):
        assert redact_params(None) == {}

    def test_removes_cms_signing_keys(self):
        params = {"locale": "de-DE", "Policy": "p", "Signature": "s", "Key-Pair-Id": "k"}

        assert redact_params(params) == {"locale": "de-DE"}

    def test_removes_keys_containing_token_case_insensitive(self):
        params = {"access_token": "a", "refresh_TOKEN": "r", "Token": "t", "n": 20}

        assert redact_params(params) == {"n": 20}

    def test_keeps_other_keys_and_values_unchanged(self):
        params = {"locale": "de-DE", "n": 50, "start": 0, "preferred_audio_language": "ja-JP"}

        assert redact_params(params) == params

    def test_does_not_mutate_input_and_returns_new_dict(self):
        params = {"locale": "de-DE", "Policy": "p", "access_token": "a"}
        original = dict(params)

        result = redact_params(params)

        assert params == original
        assert result is not params


class TestSummarizeResponseRobustness:
    def test_none_returns_no_data_marker(self):
        assert "<no data>" in summarize_response(None)

    @pytest.mark.parametrize("data", [{}, [], "plain text", 42, {"data": None}, {"items": "not a list"}])
    def test_never_raises_for_odd_input(self, data):
        assert isinstance(summarize_response(data), str)


class TestSummarizeResponseListings:
    def test_total_and_meta_are_included(self, captured):
        summary = summarize_response(captured["episodes_response"])

        assert "total=24" in summary
        assert "meta=" in summary
        assert "versions_considered" in summary

    def test_episode_item_line_from_data_key(self, captured):
        first = captured["episodes_response"]["data"][0]
        assert first["id"] == "G50UMN15P"

        summary = summarize_response(captured["episodes_response"])
        line = next(line for line in summary.splitlines() if "id=G50UMN15P" in line)

        assert "audio=de-DE" in line
        assert "season=GY19CPGQ9" in line
        assert "series=GQWH0M1J3" in line
        assert "versions=[" in line
        assert "ja-JP:GWDU7MQW8/GYE5CQNJ2" in line
        assert "de-DE:G50UMN15P/GY19CPGQ9" in line

    def test_one_line_per_item(self, captured):
        summary = summarize_response(captured["episodes_response"])
        item_lines = [line for line in summary.splitlines() if "id=" in line]

        assert len(item_lines) == 20

    def test_season_versions_without_season_guid(self, captured):
        summary = summarize_response(captured["seasons_response"])
        line = next(line for line in summary.splitlines() if "id=GY19CPGQ9" in line)

        assert "total=1" in summary
        assert "audio=de-DE" in line
        assert "series=GQWH0M1J3" in line
        assert "ja-JP:GYE5CQNJ2" in line
        assert "ja-JP:GYE5CQNJ2/" not in line

    def test_watchlist_uses_panel_and_episode_metadata(self, captured):
        panel = captured["watchlist_response"]["items"][0]["panel"]
        assert panel["id"] == "GE00380136JAJP"

        summary = summarize_response(captured["watchlist_response"])
        line = next(line for line in summary.splitlines() if "id=GE00380136JAJP" in line)

        assert "total=271" in summary
        assert "audio=ja-JP" in line
        assert "season=GS00380130JAJP" in line
        assert "series=GR9P57W96" in line
        assert "type=episode" in line
        assert "de-DE:GE00380136DEDE/GS00380130DEDE" in line

    def test_browse_items_from_items_key_with_type(self, captured):
        first = captured["browse_response"]["items"][0]
        assert first["type"] == "series"

        summary = summarize_response(captured["browse_response"])
        line = next(line for line in summary.splitlines() if f"id={first['id']}" in line)

        assert "total=1549" in summary
        assert "type=series" in line

    def test_search_nested_items_are_flattened(self, captured):
        nested_first = captured["search_response"]["items"][0]["items"][0]
        assert nested_first["id"] == "GRMG8ZQZR"

        summary = summarize_response(captured["search_response"])
        line = next(line for line in summary.splitlines() if "id=GRMG8ZQZR" in line)

        assert "type=series" in line

    def test_more_than_twenty_items_are_truncated(self):
        data = {"total": 25, "data": [{"id": f"ID{i:02d}"} for i in range(25)]}

        summary = summarize_response(data)
        item_lines = [line for line in summary.splitlines() if "id=ID" in line]

        assert len(item_lines) == 20
        assert "id=ID19" in summary
        assert "id=ID20" not in summary
        assert "+5 more" in summary

    def test_exactly_twenty_items_have_no_more_line(self):
        data = {"data": [{"id": f"ID{i:02d}"} for i in range(20)]}

        assert "more" not in summarize_response(data)


class TestSummarizeResponsePlayback:
    def test_playback_response_summary(self):
        data = {
            "audioLocale": "ja-JP",
            "hardSubs": {"en-US": {"url": "x"}, "de-DE": {"url": "y"}},
            "subtitles": {"fr-FR": {"url": "a"}, "de-DE": {"url": "b"}},
            "url": "https://example.com/manifest.mpd",
        }

        summary = summarize_response(data)

        assert "audioLocale=ja-JP" in summary
        assert "hardSubs=[de-DE, en-US]" in summary
        assert "subtitles=[de-DE, fr-FR]" in summary
        assert "url=yes" in summary

    def test_playback_response_without_url(self):
        data = {"audioLocale": "de-DE", "hardSubs": {}, "subtitles": {}}

        summary = summarize_response(data)

        assert "audioLocale=de-DE" in summary
        assert "url=no" in summary


class TestSummarizeResponseErrors:
    def test_error_key_is_reported(self):
        assert "error=invalid_grant" in summarize_response({"error": "invalid_grant"})

    def test_code_key_is_reported(self):
        summary = summarize_response({"code": "TOO_MANY_ACTIVE_STREAMS", "message": "nope"})

        assert "code=TOO_MANY_ACTIVE_STREAMS" in summary


class TestIsTraceEnabled:
    def test_none_args_is_disabled(self):
        assert is_trace_enabled(None) is False

    def test_setting_false_is_disabled(self):
        assert is_trace_enabled(make_args("false")) is False

    def test_setting_true_is_enabled(self):
        assert is_trace_enabled(make_args("true")) is True

    def test_reads_debug_logging_setting(self):
        args = make_args("true")

        is_trace_enabled(args)

        args.addon.getSetting.assert_any_call("debug_logging")


class TestApiTraceIntegration:
    URL = "https://www.crunchyroll.com/content/v2/cms/seasons/GY19CPGQ9/episodes"
    EXTERNAL_URL = "https://example.com/skip-events/G50UMN15P.json"
    BODY = {"total": 1, "data": [{"id": "TRACEITEM1", "audio_locale": "de-DE"}]}

    def run_scraper_request(self, api: API) -> list:
        scraper = Mock()
        scraper.request.return_value = make_json_response(self.BODY)
        with patch.object(api, "is_token_valid", return_value=True), patch.object(
            api.auth_manager, "create_auth_scraper", return_value=scraper
        ), patch("resources.lib.api.crunchy_log") as mock_log:
            api.make_scraper_request("GET", self.URL, params={"locale": "de-DE"})
        return logged_messages(mock_log)

    def run_unauthenticated_request(self, api: API) -> list:
        send_response = make_json_response(self.BODY)
        with patch.object(api.http, "send", return_value=send_response), patch(
            "resources.lib.api.crunchy_log"
        ) as mock_log:
            api.make_unauthenticated_request("GET", self.EXTERNAL_URL, params={"locale": "de-DE"})
        return logged_messages(mock_log)

    @staticmethod
    def assert_request_trace(messages: list, url: str) -> None:
        requests_logged = [m for m in messages if m.startswith(f"API >> GET {url}")]
        assert requests_logged, f"no request trace in {messages}"
        request_line = requests_logged[0]
        assert "locale" in request_line
        assert "de-DE" in request_line
        for secret in (CMS_POLICY, CMS_SIGNATURE, CMS_KEY_PAIR_ID, ACCESS_TOKEN):
            assert secret not in request_line

    @staticmethod
    def assert_response_trace(messages: list) -> None:
        responses_logged = [m for m in messages if m.startswith("API << HTTP 200")]
        assert responses_logged, f"no response trace in {messages}"
        assert "id=TRACEITEM1" in responses_logged[0]
        assert "total=1" in responses_logged[0]

    @staticmethod
    def assert_no_trace(messages: list) -> None:
        assert not [m for m in messages if m.startswith("API >>") or m.startswith("API <<")]

    def test_scraper_request_traces_when_enabled(self):
        messages = self.run_scraper_request(make_api("true"))

        self.assert_request_trace(messages, self.URL)
        self.assert_response_trace(messages)

    def test_scraper_request_trace_never_leaks_secrets(self):
        messages = self.run_scraper_request(make_api("true"))

        for message in messages:
            for secret in (CMS_POLICY, CMS_SIGNATURE, CMS_KEY_PAIR_ID, ACCESS_TOKEN):
                assert secret not in message

    def test_scraper_request_silent_when_disabled(self):
        messages = self.run_scraper_request(make_api("false"))

        self.assert_no_trace(messages)

    def test_unauthenticated_request_traces_when_enabled(self):
        messages = self.run_unauthenticated_request(make_api("true"))

        self.assert_request_trace(messages, self.EXTERNAL_URL)
        self.assert_response_trace(messages)

    def test_unauthenticated_request_silent_when_disabled(self):
        messages = self.run_unauthenticated_request(make_api("false"))

        self.assert_no_trace(messages)


def make_empty_response(status_code: int = 204) -> Mock:
    response = Mock()
    response.status_code = status_code
    response.ok = 200 <= status_code < 400
    response.headers = {}
    response.text = ""
    response.raise_for_status.return_value = None
    return response


class TestRedactUrl:
    def test_replaces_clear_stream_token_and_keeps_content_id(self):
        url = API.STREAMS_ENDPOINT_CLEAR_STREAM.format(CLEAR_STREAM_CONTENT_ID, CLEAR_STREAM_TOKEN)

        assert redact_url(url) == (
            f"https://cr-play-service.prd.crunchyrollsvc.com/v1/token/{CLEAR_STREAM_CONTENT_ID}/***"
        )

    def test_query_string_is_masked_after_token(self):
        """Query strings are masked as a whole (deliberate requirement change, was: kept).

        URL query strings carry CDN signatures (hmac) and playback guids. Request parameters are
        logged separately via redact_params, so the query adds no debug value.
        """
        url = API.STREAMS_ENDPOINT_CLEAR_STREAM.format(CLEAR_STREAM_CONTENT_ID, CLEAR_STREAM_TOKEN) + "?locale=de-DE"

        assert redact_url(url) == (
            f"https://cr-play-service.prd.crunchyrollsvc.com/v1/token/{CLEAR_STREAM_CONTENT_ID}/***?***"
        )

    def test_listing_query_string_is_masked(self):
        url = "https://www.crunchyroll.com/content/v2/cms/seasons/GY19CPGQ9/episodes?locale=de-DE&n=20"

        assert redact_url(url) == "https://www.crunchyroll.com/content/v2/cms/seasons/GY19CPGQ9/episodes?***"

    def test_signed_subtitle_url_query_is_masked(self):
        redacted = redact_url(SIGNED_SUBTITLE_URL)

        assert redacted == f"{SIGNED_SUBTITLE_PATH}?***"
        for fragment in ("hmac=", "exp=", "acl="):
            assert fragment not in redacted

    def test_query_string_in_free_text_is_masked_and_text_kept(self):
        text = "connection error for https://h/p.mpd?playbackGuid=abc123 after 3 tries"

        assert redact_url(text) == "connection error for https://h/p.mpd?*** after 3 tries"

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.crunchyroll.com/content/v2/cms/seasons/GY19CPGQ9/episodes",
            "https://www.crunchyroll.com/playback/v2/G50UMN15P/tv/android_tv/play",
            "https://www.crunchyroll.com/auth/v1/token",
            "https://example.com/skip-events/G50UMN15P.json",
        ],
    )
    def test_other_urls_are_unchanged(self, url):
        assert redact_url(url) == url


class TestSignedUrlLogLines:
    """The signed subtitle URL must not reach the trace line or the LOGDEBUG request line."""

    BODY = {"total": 0, "data": []}

    def run_scraper_request(self) -> list:
        api = make_api("true")
        scraper = Mock()
        scraper.request.return_value = make_json_response(self.BODY)
        with patch.object(api, "is_token_valid", return_value=True), patch.object(
            api.auth_manager, "create_auth_scraper", return_value=scraper
        ), patch("resources.lib.api.crunchy_log") as mock_log:
            api.make_scraper_request("GET", SIGNED_SUBTITLE_URL)
        return logged_messages(mock_log)

    @staticmethod
    def single_line(messages: list, prefix: str) -> str:
        lines = [m for m in messages if m.startswith(prefix)]
        assert len(lines) == 1, f"expected one line starting with {prefix!r} in {messages}"
        return lines[0]

    def test_trace_request_line_has_no_signature(self):
        line = self.single_line(self.run_scraper_request(), "API >> GET ")

        assert "subtitle.ass?***" in line
        assert "hmac=" not in line

    def test_scraper_debug_line_has_no_signature(self):
        line = self.single_line(self.run_scraper_request(), "make_scraper_request: GET ")

        assert "subtitle.ass?***" in line
        assert "hmac=" not in line


class TestApiTraceGaps:
    URL = "https://www.crunchyroll.com/content/v2/cms/seasons/GY19CPGQ9/episodes"
    EXTERNAL_URL = "https://example.com/skip-events/G50UMN15P.json"
    BODY = {"total": 1, "data": [{"id": "TRACEITEM1", "audio_locale": "de-DE"}]}
    ERROR_BODY = {"code": "access.denied", "message": "trace-error-message"}

    def scraper_patches(self, api: API, scraper: Mock):
        return (
            patch.object(api, "is_token_valid", return_value=True),
            patch.object(api.auth_manager, "create_auth_scraper", return_value=scraper),
            patch.object(api.auth_manager, "refresh_session"),
        )

    def run_scraper(self, api: API, responses: list, call):
        scraper = Mock()
        scraper.request.side_effect = responses
        valid, create, refresh = self.scraper_patches(api, scraper)
        with valid, create, refresh, patch("resources.lib.api.crunchy_log") as mock_log:
            try:
                call()
            finally:
                self.messages = logged_messages(mock_log)
        return scraper

    @staticmethod
    def response_lines(messages: list, status: int) -> list:
        return [m for m in messages if m.startswith(f"API << HTTP {status}")]

    # --- error responses -------------------------------------------------

    def test_scraper_error_response_is_traced_and_reraised(self):
        api = make_api("true")

        with pytest.raises(CrunchyrollError) as exc_info:
            self.run_scraper(
                api,
                [make_json_response(self.ERROR_BODY, status_code=403)],
                lambda: api.make_scraper_request("GET", self.URL, params={"locale": "de-DE"}),
            )

        assert type(exc_info.value) is CrunchyrollError
        assert "trace-error-message" in str(exc_info.value)
        lines = self.response_lines(self.messages, 403)
        assert lines, f"no error response trace in {self.messages}"
        assert "CrunchyrollError" in lines[0]
        assert "trace-error-message" in lines[0]

    def test_scraper_error_response_silent_when_disabled(self):
        api = make_api("false")

        with pytest.raises(CrunchyrollError):
            self.run_scraper(
                api,
                [make_json_response(self.ERROR_BODY, status_code=403)],
                lambda: api.make_scraper_request("GET", self.URL),
            )

        assert not [m for m in self.messages if m.startswith("API <<")]

    def run_unauthenticated_error(self, api: API) -> None:
        response = make_json_response(self.ERROR_BODY, status_code=403)
        with patch.object(api.http, "send", return_value=response), patch("resources.lib.api.crunchy_log") as mock_log:
            try:
                api.make_unauthenticated_request("GET", self.EXTERNAL_URL)
            finally:
                self.messages = logged_messages(mock_log)

    def test_unauthenticated_error_response_is_traced_and_reraised(self):
        api = make_api("true")

        with pytest.raises(CrunchyrollError) as exc_info:
            self.run_unauthenticated_error(api)

        assert type(exc_info.value) is CrunchyrollError
        lines = self.response_lines(self.messages, 403)
        assert lines, f"no error response trace in {self.messages}"
        assert "CrunchyrollError" in lines[0]
        assert "trace-error-message" in lines[0]

    def test_unauthenticated_error_response_silent_when_disabled(self):
        api = make_api("false")

        with pytest.raises(CrunchyrollError):
            self.run_unauthenticated_error(api)

        assert not [m for m in self.messages if m.startswith("API <<")]

    def test_login_error_from_response_is_traced_and_reraised(self):
        api = make_api("true")

        with pytest.raises(LoginError) as exc_info:
            self.run_scraper(
                api,
                [make_json_response({"error": "invalid_grant"}, status_code=400)],
                lambda: api.make_scraper_request("GET", self.URL),
            )

        assert type(exc_info.value) is LoginError
        lines = self.response_lines(self.messages, 400)
        assert lines, f"no error response trace in {self.messages}"
        assert "LoginError" in lines[0]
        assert "Invalid login credentials" in lines[0]

    # --- 401 retry -------------------------------------------------------

    def test_401_is_traced_before_retry(self):
        api = make_api("true")
        unauthorized = make_json_response({"error": "invalid_auth_token"}, status_code=401)

        scraper = self.run_scraper(
            api,
            [unauthorized, make_json_response(self.BODY)],
            lambda: api.make_request("GET", self.URL, params={"locale": "de-DE"}),
        )

        assert scraper.request.call_count == 2
        trace = [m for m in self.messages if m.startswith("API >>") or m.startswith("API <<")]
        statuses = [m.split(" ")[0:4] if m.startswith("API <<") else m.split(" ")[0:2] for m in trace]
        assert statuses == [
            ["API", ">>"],
            ["API", "<<", "HTTP", "401"],
            ["API", ">>"],
            ["API", "<<", "HTTP", "200"],
        ], f"unexpected trace order: {trace}"
        assert "id=TRACEITEM1" in trace[-1]

    # --- token in URL path -----------------------------------------------

    def test_clear_stream_delete_does_not_trace_raw_token(self):
        api = make_api("true")
        url = API.STREAMS_ENDPOINT_CLEAR_STREAM.format(CLEAR_STREAM_CONTENT_ID, CLEAR_STREAM_TOKEN)

        self.run_scraper(api, [make_empty_response(204)], lambda: api.make_request(method="DELETE", url=url))

        request_lines = [m for m in self.messages if m.startswith("API >> DELETE")]
        assert request_lines, f"no request trace in {self.messages}"
        assert CLEAR_STREAM_CONTENT_ID in request_lines[0]
        assert "***" in request_lines[0]
        for message in self.messages:
            assert CLEAR_STREAM_TOKEN not in message


class TestApiTraceDisabledAndRobust:
    URL = "https://www.crunchyroll.com/content/v2/cms/seasons/GY19CPGQ9/episodes"
    EXTERNAL_URL = "https://example.com/skip-events/G50UMN15P.json"
    CLEAR_STREAM_URL = API.STREAMS_ENDPOINT_CLEAR_STREAM.format(CLEAR_STREAM_CONTENT_ID, CLEAR_STREAM_TOKEN)
    BODY = {"total": 1, "data": [{"id": "TRACEITEM1", "audio_locale": "de-DE"}]}
    ERROR_BODY = {"code": "access.denied", "message": "trace-error-message"}

    @staticmethod
    def scraper_returning(*responses) -> Mock:
        scraper = Mock()
        scraper.request.side_effect = list(responses)
        return scraper

    # --- disabled trace does no work -------------------------------------

    def test_disabled_scraper_request_does_not_summarize(self):
        api = make_api("false")
        scraper = self.scraper_returning(make_json_response(self.BODY))

        with patch.object(api, "is_token_valid", return_value=True), patch.object(
            api.auth_manager, "create_auth_scraper", return_value=scraper
        ), patch("resources.lib.api.summarize_response") as mock_summarize:
            api.make_scraper_request("GET", self.URL)

        mock_summarize.assert_not_called()

    def test_disabled_unauthenticated_request_does_not_summarize(self):
        api = make_api("false")

        with patch.object(api.http, "send", return_value=make_json_response(self.BODY)), patch(
            "resources.lib.api.summarize_response"
        ) as mock_summarize:
            api.make_unauthenticated_request("GET", self.EXTERNAL_URL)

        mock_summarize.assert_not_called()

    # --- args without addon ----------------------------------------------

    def test_is_trace_enabled_false_for_args_without_addon(self):
        assert is_trace_enabled(types.SimpleNamespace(device_id="x")) is False

    def test_args_without_addon_keep_original_error(self):
        api = make_api("", args=types.SimpleNamespace(device_id="x"))
        response = make_json_response(self.ERROR_BODY, status_code=403)

        with patch.object(api.http, "send", return_value=response):
            with pytest.raises(CrunchyrollError) as exc_info:
                api.make_unauthenticated_request("GET", self.EXTERNAL_URL)

        assert type(exc_info.value) is CrunchyrollError
        assert "trace-error-message" in str(exc_info.value)

    # --- error text truncation -------------------------------------------

    def test_long_error_text_is_truncated_in_trace(self):
        api = make_api("true")
        long_message = "START-" + "a" * 4980 + "-TAILMARK"
        response = make_json_response({"code": "access.denied", "message": long_message}, status_code=403)

        with patch.object(api.http, "send", return_value=response), patch("resources.lib.api.crunchy_log") as mock_log:
            with pytest.raises(CrunchyrollError) as exc_info:
                api.make_unauthenticated_request("GET", self.EXTERNAL_URL)

        assert "TAILMARK" in str(exc_info.value)
        lines = [m for m in logged_messages(mock_log) if m.startswith("API << HTTP 403")]
        assert lines, "no error response trace"
        assert "CrunchyrollError" in lines[0]
        assert len(lines[0]) < 400
        assert "TAILMARK" not in lines[0]

    # --- timeout log line redaction --------------------------------------

    @pytest.mark.parametrize("debug_logging", ["true", "false"])
    def test_timeout_log_does_not_leak_stream_token(self, debug_logging):
        api = make_api(debug_logging)
        scraper = Mock()
        scraper.request.side_effect = requests.exceptions.Timeout("timed out")

        with patch.object(api, "is_token_valid", return_value=True), patch.object(
            api.auth_manager, "create_auth_scraper", return_value=scraper
        ), patch("resources.lib.api.crunchy_log") as mock_log:
            with pytest.raises(LoginError):
                api.make_scraper_request("DELETE", self.CLEAR_STREAM_URL)

        messages = logged_messages(mock_log)
        assert messages, "expected at least one log message"
        for message in messages:
            assert CLEAR_STREAM_TOKEN not in message

    def raise_from_scraper(self, api: API, exception: Exception):
        scraper = Mock()
        scraper.request.side_effect = exception
        with patch.object(api, "is_token_valid", return_value=True), patch.object(
            api.auth_manager, "create_auth_scraper", return_value=scraper
        ), patch("resources.lib.api.crunchy_log") as mock_log:
            with pytest.raises(LoginError) as exc_info:
                api.make_scraper_request("DELETE", self.CLEAR_STREAM_URL)
        return exc_info.value, logged_messages(mock_log)

    def connection_pool_message(self) -> str:
        return (
            "HTTPSConnectionPool(host='cr-play-service.prd.crunchyrollsvc.com', port=443): "
            f"Max retries exceeded with url: {self.CLEAR_STREAM_URL}"
        )

    @pytest.mark.parametrize("debug_logging", ["true", "false"])
    @pytest.mark.parametrize(
        "exception_type",
        [requests.exceptions.ConnectionError, requests.exceptions.RequestException, RuntimeError],
    )
    def test_exception_text_log_does_not_leak_stream_token(self, exception_type, debug_logging):
        api = make_api(debug_logging)

        _, messages = self.raise_from_scraper(api, exception_type(self.connection_pool_message()))

        assert messages, "expected at least one log message"
        for message in messages:
            assert CLEAR_STREAM_TOKEN not in message

    @pytest.mark.parametrize(
        "exception_type, expected_prefix, keeps_content_id",
        [
            (requests.exceptions.ConnectionError, "Network connection failed", False),
            (requests.exceptions.RequestException, "Request failed:", True),
            (RuntimeError, "Unexpected error:", True),
        ],
    )
    def test_raised_login_error_does_not_leak_stream_token(self, exception_type, expected_prefix, keeps_content_id):
        api = make_api("false")

        error, _ = self.raise_from_scraper(api, exception_type(self.connection_pool_message()))

        assert type(error) is LoginError
        assert str(error).startswith(expected_prefix)
        assert CLEAR_STREAM_TOKEN not in str(error)
        if keeps_content_id:
            assert CLEAR_STREAM_CONTENT_ID in str(error)


class TestApiTraceDisabledRegression:
    URL = "https://www.crunchyroll.com/content/v2/cms/seasons/GY19CPGQ9/episodes"
    BODY = {"total": 1, "data": [{"id": "TRACEITEM1", "audio_locale": "de-DE"}]}
    ERROR_BODY = {"code": "access.denied", "message": "trace-error-message"}

    @staticmethod
    def run_disabled(api: API, responses: list, call):
        scraper = Mock()
        scraper.request.side_effect = responses
        with patch.object(api, "is_token_valid", return_value=True), patch.object(
            api.auth_manager, "create_auth_scraper", return_value=scraper
        ), patch.object(api.auth_manager, "refresh_session"), patch("resources.lib.api.crunchy_log") as mock_log:
            result = call()
        return result, scraper, logged_messages(mock_log)

    def test_success_returns_parsed_body(self):
        api = make_api("false")

        result, _, _ = self.run_disabled(
            api, [make_json_response(self.BODY)], lambda: api.make_scraper_request("GET", self.URL)
        )

        assert result == self.BODY

    def test_error_matches_direct_parse(self):
        with pytest.raises(CrunchyrollError) as direct:
            get_json_from_response(make_json_response(self.ERROR_BODY, status_code=403))

        api = make_api("false")
        with pytest.raises(CrunchyrollError) as via_api:
            self.run_disabled(
                api,
                [make_json_response(self.ERROR_BODY, status_code=403)],
                lambda: api.make_scraper_request("GET", self.URL),
            )

        assert type(via_api.value) is type(direct.value)
        assert str(via_api.value) == str(direct.value)

    def test_401_retry_still_works_without_trace(self):
        api = make_api("false")
        unauthorized = make_json_response({"error": "invalid_auth_token"}, status_code=401)

        result, scraper, messages = self.run_disabled(
            api, [unauthorized, make_json_response(self.BODY)], lambda: api.make_request("GET", self.URL)
        )

        assert scraper.request.call_count == 2
        assert result == self.BODY
        assert not [m for m in messages if m.startswith("API >>") or m.startswith("API <<")]
