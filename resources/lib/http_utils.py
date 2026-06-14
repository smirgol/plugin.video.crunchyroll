# Crunchyroll
# based on work by stefanodvx
# Copyright (C) 2023 smirgol
#
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

import requests
from requests import HTTPError, Response

from .models.exceptions import CrunchyrollError, LoginError

CRUNCHYROLL_UA = "Crunchyroll/ANDROIDTV/3.61.0_22341 (Android 14; en-US; Chromecast)"


def default_request_headers() -> dict:
    return {
        "User-Agent": CRUNCHYROLL_UA,
        "Content-Type": "application/x-www-form-urlencoded",
    }


def get_json_from_response(r: Response) -> dict | None:
    from .utils.logging import log_error_with_trace

    code: int = r.status_code
    response_type: str = r.headers.get("Content-Type", "")

    # no content - possibly POST/DELETE request?
    if not r or not r.text:
        try:
            r.raise_for_status()
            return None
        except HTTPError as e:
            # r.text is empty when status code cause raise
            r = e.response

    # handle plain text responses (e.g. subtitles from CDN)
    # CDN may serve subtitles as text/plain or application/octet-stream
    if response_type in ("text/plain", "application/octet-stream") and r.text[0] != "{":
        # if encoding is not provided in the response, Requests will make an educated guess and very likely fail
        # messing encoding up - which did cost me hours. We will always receive utf-8 from crunchy, so enforce that
        r.encoding = "utf-8"
        return {"data": r.text}

    if not r.ok and (r.text[0] != "{"):
        raise CrunchyrollError(f"[{code}] {r.text}")

    try:
        r_json: dict = r.json()
    except (requests.exceptions.JSONDecodeError, ValueError):
        log_error_with_trace("Failed to parse response data")
        return None

    if "error" in r_json:
        error_code = r_json.get("error")
        if error_code == "invalid_grant":
            raise LoginError(f"[{code}] Invalid login credentials.")
    elif "message" in r_json and "code" in r_json:
        message = r_json.get("message")
        raise CrunchyrollError(f"[{code}] Error occurred: {message}")
    if not r.ok:
        raise CrunchyrollError(f"[{code}] {r.text}")

    return r_json
