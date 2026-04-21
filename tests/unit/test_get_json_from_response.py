from unittest.mock import Mock, patch

import pytest
import requests

from resources.lib.api import get_json_from_response
from resources.lib.model import CrunchyrollError, LoginError

ASS_CONTENT = "[Script Info]\nTitle: Test\n"


def _mock_response(content_type: str, text: str, status_code: int = 200, ok: bool = True) -> Mock:
    r = Mock()
    r.ok = ok
    r.status_code = status_code
    r.text = text
    r.headers = {"Content-Type": content_type}
    r.encoding = None
    r.json.return_value = {}
    return r


class TestPlainTextResponses:

    def test_text_plain_returns_data_dict(self):
        r = _mock_response("text/plain", ASS_CONTENT)
        assert get_json_from_response(r) == {"data": ASS_CONTENT}

    def test_octet_stream_returns_data_dict(self):
        r = _mock_response("application/octet-stream", ASS_CONTENT)
        assert get_json_from_response(r) == {"data": ASS_CONTENT}

    def test_text_plain_sets_utf8_encoding(self):
        r = _mock_response("text/plain", ASS_CONTENT)
        get_json_from_response(r)
        assert r.encoding == "utf-8"

    def test_octet_stream_sets_utf8_encoding(self):
        r = _mock_response("application/octet-stream", ASS_CONTENT)
        get_json_from_response(r)
        assert r.encoding == "utf-8"


class TestJsonResponses:

    def test_valid_json_returns_parsed_dict(self):
        r = _mock_response("application/json", '{"items": [], "total": 0}')
        r.json.return_value = {"items": [], "total": 0}
        assert get_json_from_response(r) == {"items": [], "total": 0}

    def test_json_decode_error_returns_none(self):
        r = _mock_response("application/json", "not json")
        r.json.side_effect = requests.exceptions.JSONDecodeError("", "", 0)
        with patch("resources.lib.utils.log_error_with_trace"):
            assert get_json_from_response(r) is None

    def test_error_response_raises_crunchyroll_error(self):
        r = _mock_response("application/json", '{"message": "Not found", "code": "not_found"}',
                           status_code=404, ok=False)
        r.json.return_value = {"message": "Not found", "code": "not_found"}
        with pytest.raises(CrunchyrollError):
            get_json_from_response(r)

    def test_invalid_grant_raises_login_error(self):
        r = _mock_response("application/json", '{"error": "invalid_grant"}',
                           status_code=400, ok=False)
        r.json.return_value = {"error": "invalid_grant"}
        with pytest.raises(LoginError):
            get_json_from_response(r)