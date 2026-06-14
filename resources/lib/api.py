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

import time
from datetime import datetime, timedelta

import requests
import xbmc

from ..modules import cloudscraper
from . import utils
from .auth import AuthManager
from .http_utils import default_request_headers, get_json_from_response
from .model import AccountData, CrunchyrollError, LoginError, ProfileData


class API:
    """Api documentation
    https://github.com/CloudMax94/crunchyroll-api/wiki/Api
    """

    # User Agent - single device-only identity
    CRUNCHYROLL_UA = "Crunchyroll/ANDROIDTV/3.61.0_22341 (Android 14; en-US; Chromecast)"
    # Authentication credentials - single device-only identity (AndroidTV for device auth)
    AUTHORIZATION = "Basic bm1oaGcwbDZ4eXhjZm02aHQ2aGY6SjR6bU1mdjNkMVFkWHk4dDk2d1NjeDdoUnkzclBHLTM="

    # Content endpoints (beta-api) - Keep existing for cross-domain compatibility
    INDEX_ENDPOINT = "https://beta-api.crunchyroll.com/index/v2"
    PROFILE_ENDPOINT = "https://beta-api.crunchyroll.com/accounts/v1/me/profile"

    # Authentication endpoints (www) - Required for device code flow with cloudscraper
    TOKEN_ENDPOINT = "https://www.crunchyroll.com/auth/v1/token"
    DEVICE_CODE_ENDPOINT = "https://www.crunchyroll.com/auth/v1/device/code"
    DEVICE_TOKEN_ENDPOINT = "https://www.crunchyroll.com/auth/v1/device/token"
    SEARCH_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/search"
    STREAMS_ENDPOINT = "https://beta-api.crunchyroll.com/cms/v2{}/videos/{}/streams"
    STREAMS_ENDPOINT_DRM_ANDROID_TV = "https://www.crunchyroll.com/playback/v2/{}/tv/android_tv/play"
    STREAMS_ENDPOINT_CLEAR_STREAM = "https://cr-play-service.prd.crunchyrollsvc.com/v1/token/{}/{}"
    STREAMS_ENDPOINT_GET_ACTIVE_STREAMS = (
        "https://cr-play-service.prd.crunchyrollsvc.com/playback/v1/sessions/streaming"
    )
    SEASONS_ENDPOINT = "https://www.crunchyroll.com/content/v2/cms/series/{}/seasons"
    EPISODES_ENDPOINT = "https://www.crunchyroll.com/content/v2/cms/seasons/{}/episodes"
    OBJECTS_BY_ID_LIST_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/cms/objects/{}"

    BROWSE_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/browse"
    # there is also a v2, but that will only deliver content_ids and no details about the entries
    WATCHLIST_LIST_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/{}/watchlist"
    # only v2 will allow removal of watchlist entries.
    # !!!! be super careful and always provide a content_id, or it will delete the whole playlist! *sighs* !!!!
    # WATCHLIST_REMOVE_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/watchlist/{}"
    WATCHLIST_V2_ENDPOINT = "https://www.crunchyroll.com/content/v2/{}/watchlist"
    PLAYHEADS_ENDPOINT = "https://www.crunchyroll.com/content/v2/{}/playheads"
    HISTORY_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/watch-history"
    RESUME_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/discover/{}/history"
    SEASONAL_TAGS_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/discover/seasonal_tags"
    CATEGORIES_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/tenant_categories"
    SKIP_EVENTS_ENDPOINT = "https://static.crunchyroll.com/skip-events/production/{}.json"  # request w/o auth req.
    INTRO_V2_ENDPOINT = "https://static.crunchyroll.com/datalab-intro-v2/{}.json"

    CRUNCHYLISTS_LISTS_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/custom-lists"
    CRUNCHYLISTS_VIEW_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/custom-lists/{}"

    # Device code configuration
    DEVICE_CODE_POLL_INTERVAL = 5  # seconds - initial polling interval
    DEVICE_CODE_MAX_INTERVAL = 30  # seconds - maximum polling interval with backoff
    DEVICE_CODE_TIMEOUT = 300  # seconds - device code expiration time (5 minutes)

    LICENSE_ENDPOINT = "https://cr-license-proxy.prd.crunchyrollsvc.com/v1/license/widevine"

    PROFILES_LIST_ENDPOINT = "https://beta-api.crunchyroll.com/accounts/v1/me/multiprofile"
    STATIC_IMG_PROFILE = "https://static.crunchyroll.com/assets/avatar/170x170/"
    STATIC_WALLPAPER_PROFILE = "https://static.crunchyroll.com/assets/wallpaper/720x180/"

    def __init__(self, locale: str = "en-US") -> None:
        self.http = requests.Session()
        self.locale: str = locale
        self.account_data: AccountData = AccountData(dict())
        self.profile_data: ProfileData = ProfileData(dict())
        self.api_headers: dict = default_request_headers()
        self.refresh_attempts = 0
        self.auth_manager = AuthManager(self)

    def start(self) -> None:
        self.auth_manager.start()

    def create_session(self, action: str = "login", profile_id: str | None = None) -> None:
        self.auth_manager.create_session(action=action, profile_id=profile_id)

    def close(self) -> None:
        """Saves cookies and session"""
        # no longer required, data is saved upon session update already

    def delete_account_data(self):
        self.account_data.delete_storage()

    def destroy(self) -> None:
        """Destroys session"""
        self.account_data.delete_storage()
        self.profile_data.delete_storage()

    def is_token_valid(self) -> bool:
        return self.auth_manager.is_token_valid()

    def create_auth_scraper(self):
        try:
            scraper = cloudscraper.create_scraper(
                delay=10,
                browser={"custom": self.CRUNCHYROLL_UA},
            )
            utils.crunchy_log("CloudScraper initialized for auth endpoints", xbmc.LOGDEBUG)
            return scraper
        except Exception as e:
            utils.crunchy_log(f"CloudScraper initialization failed: {e}", xbmc.LOGDEBUG)
            return None

    def request_device_code(self) -> dict | None:
        return self.auth_manager.request_device_code()

    def poll_device_token(self, device_code: str) -> dict:
        return self.auth_manager.poll_device_token(device_code)

    def _handle_login_flow(self) -> None:
        self.auth_manager._handle_login_flow()

    def _handle_refresh_flow(self) -> None:
        self.auth_manager._handle_refresh_flow()

    def _handle_profile_refresh_flow(self, profile_id: str | None) -> None:
        self.auth_manager._handle_profile_refresh_flow(profile_id)

    def _handle_device_code_flow(self) -> None:
        self.auth_manager._handle_device_code_flow()

    def _process_device_token_response(self, r) -> dict:
        return self.auth_manager._process_device_token_response(r)

    def _finalize_session_from_tokens(
        self, token_response: dict, action: str = "login", profile_id: str | None = None
    ) -> None:
        self.auth_manager._finalize_session_from_tokens(token_response, action=action, profile_id=profile_id)

    def make_request(
        self,
        method: str,
        url: str,
        headers=None,
        params=None,
        data=None,
        json_data=None,
        is_retry=False,
    ) -> dict | None:
        """
        Make a request through CloudScraper. All Crunchyroll API calls are routed
        through the scraper to handle Cloudflare protection.
        """
        return self.make_scraper_request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            json_data=json_data,
            auto_refresh=True,
            is_retry=is_retry,
        )

    def make_unauthenticated_request(
        self,
        method: str,
        url: str,
        headers=None,
        params=None,
        data=None,
        json_data=None,
    ) -> dict | None:
        """Send a raw request without any session information

        Crunchyroll domain requests go through cloudscraper; other hosts use
        plain requests to avoid unnecessary challenge-solving overhead.
        """
        use_scraper = any(host in url for host in ("crunchyroll.com", "crunchyrollsvc.com"))

        if use_scraper:
            scraper = self.auth_manager.create_auth_scraper()
            if not scraper:
                raise LoginError("CloudScraper initialization failed")

            r = scraper.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                json=json_data,
                timeout=30,
            )
        else:
            req = requests.Request(method, url, data=data, params=params, headers=headers, json=json_data)
            prepped = req.prepare()
            r = self.http.send(prepped)

        return get_json_from_response(r)

    def make_scraper_request(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
        data: dict | None = None,
        json_data: dict | None = None,
        timeout: int = 30,
        auto_refresh: bool = False,
        is_retry: bool = False,
    ) -> dict | None:
        """
        Make HTTP request using CloudScraper for Cloudflare-protected endpoints.
        Only device authentication is supported.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            headers: Optional additional headers
            params: Query parameters
            data: Form data (for application/x-www-form-urlencoded)
            json_data: JSON body data
            timeout: Request timeout in seconds
            auto_refresh: Enable automatic token refresh (for content endpoints)
            is_retry: Internal flag to prevent infinite retry loops

        Returns:
            Parsed JSON response or None

        Raises:
            LoginError: For authentication errors
            CrunchyrollError: For API errors
        """
        params = params or {}
        headers = headers or {}

        if auto_refresh and self.account_data:
            if not self.is_token_valid():
                if not self.account_data.refresh_token:
                    utils.crunchy_log(
                        "CRITICAL: Token expired but no refresh token available - session not properly initialized",
                        xbmc.LOGERROR,
                    )
                    raise LoginError("Not authenticated - please restart plugin and login")

                self.refresh_attempts += 1

                if self.refresh_attempts > 3:
                    utils.crunchy_log(
                        "CRITICAL: Too many refresh attempts, stopping to prevent infinite loop",
                        xbmc.LOGERROR,
                    )
                    raise LoginError("Authentication refresh failed repeatedly - please restart addon")

                utils.crunchy_log(
                    f"Token refresh before scraper request (attempt {self.refresh_attempts}/3)",
                    xbmc.LOGINFO,
                )
                self.auth_manager._handle_refresh_flow()

        if self.account_data:
            params.update(
                {
                    "Policy": self.account_data.cms.policy,
                    "Signature": self.account_data.cms.signature,
                    "Key-Pair-Id": self.account_data.cms.key_pair_id,
                }
            )

        if not self.account_data.access_token:
            raise LoginError("Not authenticated")

        auth_headers = {
            "Authorization": f"{self.account_data.token_type} {self.account_data.access_token}",
            "User-Agent": self.CRUNCHYROLL_UA,
        }

        request_headers = {}
        request_headers.update(auth_headers)
        request_headers.update(headers)

        scraper = self.auth_manager.create_auth_scraper()
        if not scraper:
            utils.crunchy_log("CloudScraper initialization failed, cannot proceed", xbmc.LOGERROR)
            raise LoginError("CloudScraper initialization failed")

        try:
            utils.crunchy_log(f"make_scraper_request: {method} {url}", xbmc.LOGDEBUG)

            r = scraper.request(
                method=method,
                url=url,
                headers=request_headers,
                params=params,
                data=data,
                json=json_data,
                timeout=timeout,
            )

            utils.crunchy_log(f"make_scraper_request response: HTTP {r.status_code}", xbmc.LOGDEBUG)

            if r.status_code == 401 and auto_refresh and not is_retry:
                utils.crunchy_log("Request failed due to auth error, forcing token refresh and retry", xbmc.LOGERROR)
                self.account_data.expires = date_to_str(get_date() - timedelta(seconds=1))
                return self.make_scraper_request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    json_data=json_data,
                    timeout=timeout,
                    auto_refresh=auto_refresh,
                    is_retry=True,
                )

            return get_json_from_response(r)

        except (LoginError, CrunchyrollError):
            raise
        except requests.exceptions.Timeout as e:
            utils.crunchy_log(f"CloudScraper request timeout: {url}", xbmc.LOGERROR)
            raise LoginError("Request timeout - check your network connection") from e
        except requests.exceptions.ConnectionError as e:
            utils.crunchy_log(f"CloudScraper connection error: {e}", xbmc.LOGERROR)
            raise LoginError("Network connection failed") from e
        except requests.exceptions.RequestException as e:
            utils.crunchy_log(f"CloudScraper request error: {e}", xbmc.LOGERROR)
            raise LoginError(f"Request failed: {str(e)}") from e
        except Exception as e:
            utils.crunchy_log(f"Unexpected CloudScraper error: {e}", xbmc.LOGERROR)
            raise LoginError(f"Unexpected error: {str(e)}") from e


def get_date() -> datetime:
    return datetime.utcnow()


def date_to_str(date: datetime) -> str:
    return f"{date.year}-{date.month}-{date.day}T{date.hour}:{date.minute}:{date.second}Z"


def str_to_date(string: str) -> datetime:
    time_format = "%Y-%m-%dT%H:%M:%SZ"

    try:
        res = datetime.strptime(string, time_format)
    except TypeError:
        res = datetime(*(time.strptime(string, time_format)[0:6]))

    return res
