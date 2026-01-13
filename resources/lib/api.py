# -*- coding: utf-8 -*-
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
import time
from datetime import timedelta, datetime
from typing import Optional, Dict

import requests
import xbmc
import xbmcgui
from requests import HTTPError, Response

from . import utils
from .globals import G
from .model import AccountData, LoginError, ProfileData
from ..modules import cloudscraper


class API:
    """Api documentation
    https://github.com/CloudMax94/crunchyroll-api/wiki/Api
    """
    # URL = "https://api.crunchyroll.com/"
    # VERSION = "1.1.21.0"
    # TOKEN = "LNDJgOit5yaRIWN"
    # DEVICE = "com.crunchyroll.windows.desktop"
    # TIMEOUT = 30

    # User Agents - Different clients for different purposes
    CRUNCHYROLL_UA = "Crunchyroll/3.94.0 Android/14 Ktor http-client"  # Legacy UA
    CRUNCHYROLL_UA_DEVICE = "Crunchyroll/ANDROIDTV/3.49.1_22281 (Android 14; en-US; Chromecast)"  # For device auth
    CRUNCHYROLL_UA_MOBILE = "Crunchyroll/3.94.0 Android/14 Ktor http-client"  # Mobile fallback

    # Content endpoints (beta-api) - Keep existing for cross-domain compatibility
    INDEX_ENDPOINT = "https://beta-api.crunchyroll.com/index/v2"
    PROFILE_ENDPOINT = "https://beta-api.crunchyroll.com/accounts/v1/me/profile"

    # Authentication endpoints (www) - Required for device code flow with cloudscraper
    TOKEN_ENDPOINT = "https://www.crunchyroll.com/auth/v1/token"
    TOKEN_ENDPOINT_BETA = "https://beta-api.crunchyroll.com/auth/v1/token"
    DEVICE_CODE_ENDPOINT = "https://www.crunchyroll.com/auth/v1/device/code"
    DEVICE_TOKEN_ENDPOINT = "https://www.crunchyroll.com/auth/v1/device/token"
    SEARCH_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/search"
    STREAMS_ENDPOINT = "https://beta-api.crunchyroll.com/cms/v2{}/videos/{}/streams"
    STREAMS_ENDPOINT_DRM = "https://cr-play-service.prd.crunchyrollsvc.com/v1/{}/android/phone/play"
    STREAMS_ENDPOINT_DRM_ANDROID_TV = "https://www.crunchyroll.com/playback/v2/{}/tv/android_tv/play"
    STREAMS_ENDPOINT_CLEAR_STREAM = "https://cr-play-service.prd.crunchyrollsvc.com/v1/token/{}/{}"
    STREAMS_ENDPOINT_GET_ACTIVE_STREAMS = "https://cr-play-service.prd.crunchyrollsvc.com/playback/v1/sessions/streaming"
    # SERIES_ENDPOINT = "https://beta-api.crunchyroll.com/cms/v2{}/series/{}"
    SEASONS_ENDPOINT = "https://beta-api.crunchyroll.com/cms/v2{}/seasons"
    EPISODES_ENDPOINT = "https://beta-api.crunchyroll.com/cms/v2{}/episodes"
    OBJECTS_BY_ID_LIST_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/cms/objects/{}"
    # SIMILAR_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/{}/similar_to"
    # NEWSFEED_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/news_feed"
    BROWSE_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/browse"
    # there is also a v2, but that will only deliver content_ids and no details about the entries
    WATCHLIST_LIST_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/{}/watchlist"
    # only v2 will allow removal of watchlist entries.
    # !!!! be super careful and always provide a content_id, or it will delete the whole playlist! *sighs* !!!!
    # WATCHLIST_REMOVE_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/watchlist/{}"
    #WATCHLIST_V2_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/watchlist"
    WATCHLIST_V2_ENDPOINT = "https://www.crunchyroll.com/content/v2/{}/watchlist"
    #PLAYHEADS_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/playheads"
    PLAYHEADS_ENDPOINT = "https://www.crunchyroll.com/content/v2/{}/playheads"
    HISTORY_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/watch-history"
    RESUME_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/discover/{}/history"
    SEASONAL_TAGS_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/discover/seasonal_tags"
    CATEGORIES_ENDPOINT = "https://beta-api.crunchyroll.com/content/v1/tenant_categories"
    SKIP_EVENTS_ENDPOINT = "https://static.crunchyroll.com/skip-events/production/{}.json"  # request w/o auth req.
    INTRO_V2_ENDPOINT = "https://static.crunchyroll.com/datalab-intro-v2/{}.json"

    CRUNCHYLISTS_LISTS_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/custom-lists"
    CRUNCHYLISTS_VIEW_ENDPOINT = "https://beta-api.crunchyroll.com/content/v2/{}/custom-lists/{}"

    # Authentication credentials - Multiple client types for different purposes
    AUTHORIZATION_DEVICE = "Basic bGtlc2k3c25zeTlvb2ptaTJyOWg6LWFHRFhGRk5UbHVaTUxZWEVSbmdOWW5FanZnSDVvZHY="  # AndroidTV for device auth
    AUTHORIZATION_MOBILE = "Basic dWtta3d2aHdsZGh0eXNrdzIydGk6XzluVTFjenJ3aFc2YjFHUjlvc3RIbHdoTEs1amlwTXI="  # Mobile fallback
    AUTHORIZATION_LEGACY = "Basic dWtta3d2aHdsZGh0eXNrdzIydGk6XzluVTFjenJ3aFc2YjFHUjlvc3RIbHdoTEs1amlwTXI="  # Legacy compatibility

    # Primary authorization (for backward compatibility)
    AUTHORIZATION = AUTHORIZATION_DEVICE

    # Device code configuration
    DEVICE_CODE_POLL_INTERVAL = 5  # seconds - initial polling interval
    DEVICE_CODE_MAX_INTERVAL = 30  # seconds - maximum polling interval with backoff
    DEVICE_CODE_TIMEOUT = 300  # seconds - device code expiration time (5 minutes)

    LICENSE_ENDPOINT = "https://cr-license-proxy.prd.crunchyrollsvc.com/v1/license/widevine"

    PROFILES_LIST_ENDPOINT = "https://beta-api.crunchyroll.com/accounts/v1/me/multiprofile"
    STATIC_IMG_PROFILE = "https://static.crunchyroll.com/assets/avatar/170x170/"
    STATIC_WALLPAPER_PROFILE = "https://static.crunchyroll.com/assets/wallpaper/720x180/"

    def __init__(
            self,
            locale: str = "en-US"
    ) -> None:
        self.http = requests.Session()
        self.locale: str = locale
        self.account_data: AccountData = AccountData(dict())
        self.profile_data: ProfileData = ProfileData(dict())
        self.api_headers: Dict = default_request_headers()
        self.refresh_attempts = 0

    def start(self) -> None:
        session_restart = G.args.get_arg('session_restart', False)

        # restore account data from file (if any)
        account_data = self.account_data.load_from_storage()

        # restore profile data from file (if any)
        self.profile_data = ProfileData(self.profile_data.load_from_storage())

        if account_data and not session_restart:
            self.account_data = AccountData(account_data)
            account_auth = {"Authorization": f"{self.account_data.token_type} {self.account_data.access_token}"}
            self.api_headers.update(account_auth)

            # Restore User-Agent from session data for persistent authentication compatibility
            user_agent_type = getattr(self.account_data, 'user_agent_type', 'mobile')
            if user_agent_type == "device":
                API.CRUNCHYROLL_UA = self.CRUNCHYROLL_UA_DEVICE
                utils.crunchy_log(f"Session restored: AndroidTV User-Agent set: {API.CRUNCHYROLL_UA}", xbmc.LOGDEBUG)
            else:
                API.CRUNCHYROLL_UA = self.CRUNCHYROLL_UA_MOBILE
                utils.crunchy_log(f"Session restored: Mobile User-Agent set: {API.CRUNCHYROLL_UA}", xbmc.LOGDEBUG)

            # Update headers with restored User-Agent
            self.api_headers = default_request_headers()
            self.api_headers.update(account_auth)
            utils.crunchy_log(f"Session start: User-Agent type '{user_agent_type}' restored from session data", xbmc.LOGDEBUG)

            # Use new token validation method
            if self.is_token_valid():
                utils.crunchy_log("Existing session is valid, skipping authentication")
                return
            else:
                utils.crunchy_log("Existing session expired, will attempt refresh")
                session_restart = True

        # session management - always use "login" action for automatic flow
        self.create_session(action="refresh" if session_restart else "login")

    def create_session(self, action: str = "login", profile_id: Optional[str] = None) -> None:
        """
        Create or refresh authentication session

        Args:
            action: "login" (auto device flow), "refresh" (refresh token), "refresh_profile" (profile switch)
            profile_id: Profile ID for profile refresh action
        """
        utils.crunchy_log(f"Creating session with action: {action}", xbmc.LOGDEBUG)

        if action == "login":
            # Modern device code authentication flow
            return self._handle_login_flow()

        elif action == "refresh":
            # Refresh existing token, fall back to device auth if refresh token expired
            try:
                return self._handle_refresh_flow()
            except LoginError as e:
                if e.error_code == "REFRESH_TOKEN_EXPIRED":
                    xbmcgui.Dialog().ok(
                        G.args.addon_name,
                        G.args.addon.getLocalizedString(30401)
                    )
                    self.account_data.delete_storage()
                    return self._handle_login_flow()
                else:
                    raise

        elif action == "refresh_profile":
            # Switch profile using existing refresh token
            return self._handle_profile_refresh_flow(profile_id)

        else:
            raise LoginError(f"Unknown action: {action}")

    def _handle_login_flow(self) -> None:
        """
        Handle login flow: check existing token → try refresh → device code → anonymous fallback
        """
        utils.crunchy_log("Starting login flow", xbmc.LOGDEBUG)

        # 1. Check if we already have a valid token
        if self.account_data.access_token and self.is_token_valid():
            utils.crunchy_log("Existing token is still valid, skipping authentication")
            return

        # 2. Try refresh if we have a refresh token
        if self.account_data.refresh_token:
            try:
                utils.crunchy_log("Attempting token refresh", xbmc.LOGDEBUG)
                self._handle_refresh_flow()
                return  # Success, exit flow
            except LoginError as e:
                utils.crunchy_log(f"Token refresh failed: {e}, continuing to device flow", xbmc.LOGDEBUG)
                # Clear invalid tokens - this is expected behavior, no user notification needed
                self.account_data.delete_storage()

        # 3. Start device code authentication flow
        try:
            utils.crunchy_log("Starting device code authentication", xbmc.LOGDEBUG)
            self._handle_device_code_flow()
            return  # Success, exit flow
        except LoginError as e:
            utils.crunchy_log(f"Device code authentication failed: {e}", xbmc.LOGERROR)
            # Device flow failure is expected during Phase 1, no notification needed

        # All authentication methods failed
        raise LoginError("Device authentication failed")

    def _handle_refresh_flow(self) -> None:
        """Handle token refresh using existing refresh token"""
        if not self.account_data.refresh_token:
            raise LoginError("No refresh token available")

        utils.crunchy_log("Refreshing authentication token", xbmc.LOGDEBUG)

        headers = {
            "Authorization": self.AUTHORIZATION_DEVICE,
            "User-Agent": self.CRUNCHYROLL_UA_DEVICE,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "refresh_token": self.account_data.refresh_token,
            "grant_type": "refresh_token",
            "scope": "offline_access",
            "device_id": G.args.device_id,
            "device_name": 'Kodi',
            "device_type": 'MediaCenter'
        }

        # Try www endpoint with cloudscraper first
        scraper = self.create_auth_scraper()
        if scraper:
            try:
                utils.crunchy_log("Trying token refresh via www endpoint with cloudscraper")
                r = scraper.post(
                    url=self.TOKEN_ENDPOINT,
                    headers=headers,
                    data=data,
                    timeout=30
                )

                if r.ok:
                    r_json = r.json()
                    utils.crunchy_log("Token refresh successful via www endpoint")
                    self._finalize_session_from_tokens(r_json, action="refresh")
                    return  # Success
                else:
                    utils.crunchy_log(f"WWW token refresh failed: {r.status_code}", xbmc.LOGDEBUG)
            except Exception as e:
                utils.crunchy_log(f"WWW token refresh error: {e}", xbmc.LOGDEBUG)
                # Network errors during refresh are recoverable, continue to fallback

        # Fallback to beta-api endpoint
        try:
            utils.crunchy_log("Trying token refresh via beta-api endpoint", xbmc.LOGDEBUG)
            headers["Authorization"] = self.AUTHORIZATION_LEGACY
            headers["User-Agent"] = self.CRUNCHYROLL_UA

            r = self.http.post(
                url=self.TOKEN_ENDPOINT_BETA,
                headers=headers,
                data=data
            )

            if r.ok:
                r_json = r.json()
                utils.crunchy_log("Token refresh successful via beta-api endpoint")
                self._finalize_session_from_tokens(r_json, action="refresh")
                return  # Success
            else:
                utils.crunchy_log(f"Beta-api token refresh failed: {r.status_code}", xbmc.LOGDEBUG)
                if r.status_code == 400:
                    # Refresh token expired/invalid
                    raise LoginError("Refresh token expired", error_code="REFRESH_TOKEN_EXPIRED")
                elif r.status_code >= 500:
                    # Server errors
                    utils.crunchy_log("Server error during token refresh", xbmc.LOGERROR)
                    raise LoginError("Server error", error_code="SERVER_ERROR")

        except requests.exceptions.RequestException as e:
            # Network connectivity issues
            utils.crunchy_log(f"Network error during token refresh: {e}", xbmc.LOGERROR)
            raise LoginError("Network error")
        except Exception as e:
            utils.crunchy_log(f"Unexpected token refresh error: {e}", xbmc.LOGERROR)
            raise LoginError(f"Unexpected error during token refresh: {str(e)}")

        raise LoginError("Token refresh failed on all endpoints")

    def _handle_profile_refresh_flow(self, profile_id: Optional[str]) -> None:
        """Handle profile refresh using existing refresh token"""
        if not profile_id:
            raise LoginError("Profile ID required for profile refresh")

        if not self.account_data.refresh_token:
            raise LoginError("No refresh token available for profile refresh")

        utils.crunchy_log(f"Refreshing profile: {profile_id}", xbmc.LOGDEBUG)

        headers = {
            "Authorization": self.AUTHORIZATION_DEVICE,
            "User-Agent": self.CRUNCHYROLL_UA_DEVICE,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "device_id": G.args.device_id,
            "device_name": 'Kodi',
            "device_type": "MediaCenter",
            "grant_type": "refresh_token_profile_id",
            "profile_id": profile_id,
            "refresh_token": self.account_data.refresh_token
        }

        # Try www endpoint with cloudscraper first
        scraper = self.create_auth_scraper()
        if scraper:
            try:
                utils.crunchy_log("Trying profile refresh via www endpoint with cloudscraper", xbmc.LOGDEBUG)
                r = scraper.post(
                    url=self.TOKEN_ENDPOINT,
                    headers=headers,
                    data=data,
                    timeout=30
                )

                if r.ok:
                    r_json = r.json()
                    utils.crunchy_log("Profile refresh successful via www endpoint")
                    self._finalize_session_from_tokens(r_json, action="refresh_profile", profile_id=profile_id)
                    return  # Success
                else:
                    utils.crunchy_log(f"WWW profile refresh failed: {r.status_code}", xbmc.LOGDEBUG)
            except Exception as e:
                utils.crunchy_log(f"WWW profile refresh error: {e}", xbmc.LOGDEBUG)

        # Fallback to beta-api endpoint
        try:
            utils.crunchy_log("Trying profile refresh via beta-api endpoint", xbmc.LOGDEBUG)
            headers["Authorization"] = self.AUTHORIZATION_LEGACY
            headers["User-Agent"] = self.CRUNCHYROLL_UA

            r = self.http.post(
                url=self.TOKEN_ENDPOINT_BETA,
                headers=headers,
                data=data
            )

            if r.ok:
                r_json = r.json()
                utils.crunchy_log("Profile refresh successful via beta-api endpoint")
                self._finalize_session_from_tokens(r_json, action="refresh_profile", profile_id=profile_id)
                return  # Success
            else:
                utils.crunchy_log(f"Beta-api profile refresh failed: {r.status_code}", xbmc.LOGDEBUG)

        except requests.exceptions.RequestException as e:
            # Network connectivity issues
            utils.crunchy_log(f"Network error during profile refresh: {e}", xbmc.LOGERROR)
            raise LoginError("Network connection failed during profile switch")
        except Exception as e:
            utils.crunchy_log(f"Unexpected profile refresh error: {e}", xbmc.LOGERROR)
            raise LoginError(f"Unexpected error during profile refresh: {str(e)}")

        raise LoginError("Profile refresh failed on all endpoints")

    def _handle_device_code_flow(self) -> None:
        """Handle device code authentication flow with UI dialog"""
        utils.crunchy_log("Starting device code authentication flow", xbmc.LOGDEBUG)

        try:
            # 1. Request device code
            device_code_data = self.request_device_code()
            if not device_code_data:
                raise LoginError("Failed to request device code")

            utils.crunchy_log(f"Device code received: {device_code_data.get('user_code', 'N/A')}", xbmc.LOGDEBUG)

            # 2. Show activation dialog (this handles polling internally)
            from .gui import show_device_activation_dialog
            dialog_result = show_device_activation_dialog(device_code_data, self)

            # 3. Handle dialog result
            if dialog_result["status"] == "success":
                # Authentication successful - finalize session
                auth_result = dialog_result["auth_result"]
                utils.crunchy_log("Device authentication successful, finalizing session")
                self._finalize_session_from_tokens(auth_result, action="device")
                return  # Success

            elif dialog_result["status"] == "cancelled":
                utils.crunchy_log("Device authentication cancelled by user", xbmc.LOGDEBUG)
                raise LoginError("Device authentication cancelled by user")

            elif dialog_result["status"] == "expired":
                utils.crunchy_log("Device code expired during authentication", xbmc.LOGDEBUG)
                raise LoginError("Device code expired - please try again")

            else:
                # Error case
                error_msg = dialog_result.get("message", "Unknown dialog error")
                utils.crunchy_log(f"Device authentication dialog error: {error_msg}", xbmc.LOGDEBUG)
                raise LoginError(f"Device authentication failed: {error_msg}")

        except LoginError:
            # Re-raise LoginErrors as-is (expected flow control)
            raise
        except Exception as e:
            # Unexpected errors during device flow
            utils.crunchy_log(f"Unexpected device code flow error: {e}", xbmc.LOGERROR)
            raise LoginError(f"Device authentication error: {str(e)}")


    def close(self) -> None:
        """Saves cookies and session
        """
        # no longer required, data is saved upon session update already

    def destroy(self) -> None:
        """Destroys session
        """
        self.account_data.delete_storage()
        self.profile_data.delete_storage()

    def is_token_valid(self) -> bool:
        """
        Check if current access token is valid and not expired

        Returns:
            bool: True if token exists and is not expired (with 60s buffer)
        """
        utils.crunchy_log("Checking token validity", xbmc.LOGDEBUG)

        if not self.account_data.access_token:
            utils.crunchy_log("Token validation failed - no access token", xbmc.LOGDEBUG)
            return False

        if not self.account_data.expires:
            utils.crunchy_log("Token validation failed - no expiration date", xbmc.LOGDEBUG)
            return False

        try:
            current_time = get_date()
            expiry_time = str_to_date(self.account_data.expires)
            time_until_expiry = expiry_time - current_time

            utils.crunchy_log(f"Current time: {current_time}", xbmc.LOGDEBUG)
            utils.crunchy_log(f"Expiry time: {expiry_time}", xbmc.LOGDEBUG)
            utils.crunchy_log(f"Time until expiry: {time_until_expiry}", xbmc.LOGDEBUG)

            # Add 60 second buffer to avoid edge cases (network delays, clock skew)
            is_valid = current_time < (expiry_time - timedelta(seconds=60))
            utils.crunchy_log(f"Token is valid (with 60s buffer): {is_valid}", xbmc.LOGDEBUG)

            return is_valid
        except Exception as e:
            # If we can't parse expiration date, assume token is invalid
            utils.crunchy_log(f"Token validation exception: {e}", xbmc.LOGDEBUG)
            return False

    def create_auth_scraper(self):
        """
        Create cloudscraper instance for www auth endpoints

        Returns:
            CloudScraper instance configured for Crunchyroll auth endpoints
            None if cloudscraper initialization fails
        """
        try:
            scraper = cloudscraper.create_scraper(
                delay=10,
                browser={'custom': self.CRUNCHYROLL_UA_DEVICE}
            )
            utils.crunchy_log("CloudScraper initialized for auth endpoints", xbmc.LOGDEBUG)
            return scraper
        except Exception as e:
            utils.crunchy_log(f"CloudScraper initialization failed: {e}", xbmc.LOGDEBUG)
            return None

    def request_device_code(self) -> Optional[Dict]:
        """
        Request device code for activation flow

        Returns:
            Dict with device_code, user_code, verification_uri, expires_in, interval
            None if request fails
        """
        headers = {
            "Authorization": self.AUTHORIZATION_DEVICE,
            "User-Agent": self.CRUNCHYROLL_UA_DEVICE,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Try with cloudscraper first (required for www endpoints)
        scraper = self.create_auth_scraper()
        if scraper:
            try:
                utils.crunchy_log("Requesting device code with cloudscraper", xbmc.LOGDEBUG)
                r = scraper.post(
                    url=self.DEVICE_CODE_ENDPOINT,
                    headers=headers,
                    data={},
                    timeout=30
                )

                if r.ok:
                    r_json = r.json()
                    if 'user_code' in r_json and 'device_code' in r_json:
                        utils.crunchy_log(f"Device code received via cloudscraper: {r_json.get('user_code', 'N/A')}", xbmc.LOGDEBUG)
                        return r_json
                    else:
                        utils.crunchy_log("Device code response missing required fields", xbmc.LOGDEBUG)
                        return None
                else:
                    utils.crunchy_log(f"Device code request failed via cloudscraper: {r.status_code}", xbmc.LOGDEBUG)
            except Exception as e:
                utils.crunchy_log(f"Device code request via cloudscraper failed: {e}", xbmc.LOGDEBUG)

        # Fallback to regular requests (will likely fail with 403 for www)
        try:
            utils.crunchy_log("Trying device code request with regular requests", xbmc.LOGDEBUG)
            r = self.http.post(
                url=self.DEVICE_CODE_ENDPOINT,
                headers=headers,
                data={}
            )

            if r.ok:
                r_json = r.json()
                if 'user_code' in r_json and 'device_code' in r_json:
                    utils.crunchy_log(f"Device code received via requests: {r_json.get('user_code', 'N/A')}", xbmc.LOGDEBUG)
                    return r_json
                else:
                    utils.crunchy_log("Device code response missing required fields", xbmc.LOGDEBUG)
                    return None
            else:
                utils.crunchy_log(f"Device code request failed: {r.status_code} {r.text}", xbmc.LOGDEBUG)
                return None

        except Exception as e:
            utils.crunchy_log(f"Device code request error: {e}", xbmc.LOGDEBUG)
            return None

    def poll_device_token(self, device_code: str) -> Dict:
        """
        Poll for device token after user activation

        Args:
            device_code: Device code from request_device_code()

        Returns:
            Dict with status and data:
            - {"status": "success", "data": {...}} - Token received
            - {"status": "pending"} - User hasn't activated yet, continue polling
            - {"status": "expired"} - Device code expired, need new code
            - {"status": "error", "message": "..."} - Unrecoverable error
        """
        headers = {
            "Authorization": self.AUTHORIZATION_DEVICE,
            "User-Agent": self.CRUNCHYROLL_UA_DEVICE,
            "Accept": "application/json",
            "Accept-Charset": "UTF-8",
            "Content-Type": "application/json"
        }

        # Try with cloudscraper first (required for www endpoints)
        scraper = self.create_auth_scraper()
        if scraper:
            try:
                r = scraper.post(
                    url=self.DEVICE_TOKEN_ENDPOINT,
                    headers=headers,
                    json={"device_code": device_code},
                    timeout=30
                )
                return self._process_device_token_response(r, "cloudscraper")
            except Exception as e:
                utils.crunchy_log(f"Device token poll via cloudscraper failed: {e}", xbmc.LOGDEBUG)

        # Fallback to regular requests
        try:
            r = self.http.post(
                url=self.DEVICE_TOKEN_ENDPOINT,
                headers=headers,
                json={"device_code": device_code}
            )
            return self._process_device_token_response(r, "requests")

        except Exception as e:
            utils.crunchy_log(f"Device token poll error: {e}", xbmc.LOGDEBUG)
            return {"status": "error", "message": f"Network error: {str(e)}"}

    def _process_device_token_response(self, r, method_name: str) -> Dict:
        """
        Process device token response from either cloudscraper or requests

        Args:
            r: Response object
            method_name: "cloudscraper" or "requests" for logging

        Returns:
            Status dict as defined in poll_device_token
        """
        try:
            # Enhanced logging for debugging
            utils.crunchy_log(f"Device token response via {method_name}: HTTP {r.status_code}", xbmc.LOGDEBUG)
            utils.crunchy_log(f"Response headers: {dict(r.headers)}", xbmc.LOGDEBUG)
            utils.crunchy_log(f"Response content length: {len(r.text)}", xbmc.LOGDEBUG)
            utils.crunchy_log(f"Response content (first 500 chars): {r.text[:500]}", xbmc.LOGDEBUG)

            if r.ok:
                # Handle HTTP 204 No Content (authentication acknowledged but may need retry)
                if r.status_code == 204:
                    utils.crunchy_log(f"Device authentication acknowledged (HTTP 204) via {method_name}", xbmc.LOGDEBUG)
                    # HTTP 204 means server acknowledged but tokens not ready yet
                    return {"status": "pending"}

                # Check if we have content to parse
                if len(r.text.strip()) == 0:
                    utils.crunchy_log(f"Empty response body via {method_name}", xbmc.LOGDEBUG)
                    return {"status": "error", "message": "Empty response from server"}

                # Check content type
                content_type = r.headers.get('content-type', '').lower()
                if 'application/json' not in content_type and content_type != '':
                    utils.crunchy_log(f"Unexpected content-type: {content_type} via {method_name}", xbmc.LOGDEBUG)
                    return {"status": "error", "message": f"Server returned non-JSON response: {content_type}"}

                # Try to parse JSON
                try:
                    r_json = r.json()
                    utils.crunchy_log(f"Parsed JSON response via {method_name}: {r_json}", xbmc.LOGDEBUG)
                except ValueError as json_error:
                    utils.crunchy_log(f"JSON parsing failed via {method_name}: {json_error}", xbmc.LOGDEBUG)
                    utils.crunchy_log(f"Raw response text: '{r.text}'", xbmc.LOGDEBUG)
                    return {"status": "error", "message": f"Invalid JSON response: {json_error}"}

                if 'access_token' in r_json:
                    utils.crunchy_log(f"Device token received successfully via {method_name}", xbmc.LOGDEBUG)
                    return {"status": "success", "data": r_json}
                else:
                    utils.crunchy_log(f"Device token response missing access_token via {method_name}: {r_json}", xbmc.LOGDEBUG)
                    return {"status": "error", "message": "Invalid token response - missing access_token"}

            elif r.status_code == 400:
                # Expected during polling - analyze specific error
                try:
                    error_json = r.json()
                    error_code = error_json.get('error', '')
                    utils.crunchy_log(f"Device polling 400 response via {method_name}: {error_json}", xbmc.LOGDEBUG)

                    if 'authorization_pending' in error_code:
                        # Normal polling state - user hasn't activated yet
                        return {"status": "pending"}
                    elif 'expired_token' in error_code:
                        utils.crunchy_log(f"Device code expired via {method_name}", xbmc.LOGDEBUG)
                        return {"status": "expired", "message": "Device code expired"}
                    elif 'access_denied' in error_code:
                        utils.crunchy_log(f"User denied device activation via {method_name}", xbmc.LOGDEBUG)
                        return {"status": "error", "message": "User denied device activation"}
                    else:
                        utils.crunchy_log(f"Device token polling error via {method_name}: {error_json}", xbmc.LOGDEBUG)
                        return {"status": "error", "message": f"Authentication error: {error_code}"}

                except ValueError as json_error:
                    utils.crunchy_log(f"Device token 400 response - JSON parsing failed via {method_name}: {json_error}", xbmc.LOGDEBUG)
                    utils.crunchy_log(f"Raw 400 response: '{r.text}'", xbmc.LOGDEBUG)
                    return {"status": "error", "message": f"Server error {r.status_code}: malformed response"}

            elif r.status_code == 403:
                # Cloudflare protection (should not happen with cloudscraper)
                utils.crunchy_log(f"Cloudflare protection detected via {method_name}: {r.text}", xbmc.LOGDEBUG)
                return {"status": "error", "message": f"Cloudflare protection detected via {method_name}"}
            elif r.status_code == 404:
                # Endpoint not found
                utils.crunchy_log(f"Device token endpoint not found via {method_name}: {r.text}", xbmc.LOGDEBUG)
                return {"status": "error", "message": "Device token endpoint not found"}
            else:
                utils.crunchy_log(f"Device token poll failed via {method_name}: HTTP {r.status_code}", xbmc.LOGDEBUG)
                utils.crunchy_log(f"Error response text: {r.text}", xbmc.LOGDEBUG)
                return {"status": "error", "message": f"HTTP error: {r.status_code}"}

        except Exception as e:
            utils.crunchy_log(f"Device token response processing error via {method_name}: {e}", xbmc.LOGERROR)
            utils.crunchy_log(f"Exception details: {type(e).__name__}: {str(e)}", xbmc.LOGDEBUG)
            return {"status": "error", "message": f"Response processing error: {str(e)}"}


    def _finalize_session_from_tokens(self, token_response: Dict, action: str = "login", profile_id: Optional[str] = None) -> None:
        """
        Finalize session setup after receiving authentication tokens

        Args:
            token_response: Dict containing access_token, token_type, refresh_token, expires_in
            action: The action that led to this finalization ("login", "refresh", "refresh_profile", "device")
            profile_id: Optional profile ID for profile refresh
        """
        try:
            utils.crunchy_log(f"Finalizing session from tokens (action: {action})", xbmc.LOGDEBUG)
            utils.crunchy_log(f"Token response keys: {list(token_response.keys()) if token_response else 'None'}", xbmc.LOGDEBUG)

            # Initialize account data, back up ua type
            existing_ua_type = getattr(self.account_data, 'user_agent_type',
                                       'mobile') if self.account_data else 'mobile'

            # Extract token information
            access_token = token_response["access_token"]
            token_type = token_response["token_type"]
            account_auth = {"Authorization": f"{token_type} {access_token}"}

            # Setup account data dictionary
            account_data = dict()
            account_data.update(token_response)

            # CRITICAL: Switch User-Agent based on authentication method and persist choice
            user_agent_type = None
            if action == "device":
                # Device authentication - use AndroidTV UA for all future requests
                utils.crunchy_log("Switching to AndroidTV User-Agent for device session", xbmc.LOGDEBUG)
                API.CRUNCHYROLL_UA = self.CRUNCHYROLL_UA_DEVICE
                user_agent_type = "device"
                utils.crunchy_log(f"User-Agent switched to AndroidTV: {API.CRUNCHYROLL_UA}", xbmc.LOGDEBUG)
            elif action == "login":
                # Regular login (legacy) - use Mobile UA
                utils.crunchy_log("Using Mobile User-Agent for legacy session", xbmc.LOGDEBUG)
                API.CRUNCHYROLL_UA = self.CRUNCHYROLL_UA_MOBILE
                user_agent_type = "mobile"
                utils.crunchy_log(f"User-Agent set to Mobile: {API.CRUNCHYROLL_UA}", xbmc.LOGDEBUG)
            elif action in ["refresh", "refresh_profile"]:
                # For refresh, get user_agent_type from existing session or default to mobile for backward compatibility
                #existing_ua_type = getattr(self.account_data, 'user_agent_type', 'mobile') if self.account_data else 'mobile'
                user_agent_type = existing_ua_type

                if user_agent_type == "device":
                    API.CRUNCHYROLL_UA = self.CRUNCHYROLL_UA_DEVICE
                    utils.crunchy_log("Token refresh: Restored AndroidTV User-Agent for device session", xbmc.LOGDEBUG)
                else:
                    API.CRUNCHYROLL_UA = self.CRUNCHYROLL_UA_MOBILE
                    utils.crunchy_log("Token refresh: Maintained Mobile User-Agent for legacy session", xbmc.LOGDEBUG)

                utils.crunchy_log(f"User-Agent restored to: {API.CRUNCHYROLL_UA}", xbmc.LOGDEBUG)

            # Store user_agent_type in session data for persistence across Kodi restarts
            account_data["user_agent_type"] = user_agent_type
            utils.crunchy_log(f"Stored user_agent_type: {user_agent_type} in session data", xbmc.LOGDEBUG)

            # Update API headers with authentication and correct UA
            self.api_headers = default_request_headers()
            self.api_headers.update(account_auth)

            # Log the User-Agent being set for session
            current_ua = self.api_headers.get('User-Agent', 'Unknown')
            utils.crunchy_log(f"Session finalized with User-Agent: {current_ua}", xbmc.LOGDEBUG)

            # Calculate and set token expiration
            account_data["expires"] = date_to_str(
                get_date() + timedelta(seconds=float(account_data["expires_in"]))
            )

            # Fetch index data (user info, account details)
            utils.crunchy_log("Fetching index data", xbmc.LOGDEBUG)
            r = self.make_unauthenticated_request(
                method="GET",
                url=API.INDEX_ENDPOINT,
                headers=self.api_headers
            )
            account_data.update(r)

            # Fetch profile data
            utils.crunchy_log("Fetching profile data", xbmc.LOGDEBUG)
            r = self.make_unauthenticated_request(
                method="GET",
                url=API.PROFILE_ENDPOINT,
                headers=self.api_headers
            )
            account_data.update(r)

            # Handle profile refresh specific logic
            if action == "refresh_profile" and profile_id:
                utils.crunchy_log(f"Refreshing profile data for profile_id: {profile_id}", xbmc.LOGDEBUG)
                # Fetch all profiles from API
                r = self.make_unauthenticated_request(
                    method="GET",
                    url=self.PROFILES_LIST_ENDPOINT,
                    headers=self.api_headers
                )

                # Extract current profile data as dict from ProfileData obj
                profile_data = vars(self.profile_data)

                # Update extracted profile data with fresh data from API for requested profile_id
                profile_data.update(
                    next(profile for profile in r.get("profiles") if profile["profile_id"] == profile_id)
                )

                # Update our ProfileData obj with updated data
                self.profile_data = ProfileData(profile_data)

                # Cache profile to file
                self.profile_data.write_to_storage()

            # Store account data
            self.account_data = AccountData(account_data)
            self.account_data.write_to_storage()

            # Reset refresh attempts counter on successful session finalization
            self.refresh_attempts = 0

            utils.crunchy_log(f"Session finalization completed successfully (action: {action})")

        except KeyError as e:
            # Missing required token fields
            error_msg = f"Invalid token response - missing field: {e}"
            utils.crunchy_log(error_msg, xbmc.LOGERROR)
            raise LoginError(f"Invalid authentication response: missing {e}")
        except Exception as e:
            # Unexpected errors during session setup
            utils.crunchy_log(f"Session finalization failed: {e}", xbmc.LOGERROR)
            raise LoginError(f"Failed to finalize session: {str(e)}")

    def make_request(
            self,
            method: str,
            url: str,
            headers=None,
            params=None,
            data=None,
            json_data=None,
            is_retry=False,
    ) -> Optional[Dict]:
        params = params or dict()
        headers = headers or dict()

        if self.account_data:
            # token refresh if expired
            if not self.is_token_valid():
                self.refresh_attempts += 1

                if self.refresh_attempts > 3:
                    utils.crunchy_log("CRITICAL: Too many refresh attempts, stopping to prevent infinite loop", xbmc.LOGERROR)
                    raise LoginError("Authentication refresh failed repeatedly - please restart addon")

                utils.crunchy_log(f"make_request_proposal: session renewal due to expired token (attempt {self.refresh_attempts}/3)", xbmc.LOGINFO)
                self._handle_refresh_flow()

            # update keys
            params.update({
                "Policy": self.account_data.cms.policy,
                "Signature": self.account_data.cms.signature,
                "Key-Pair-Id": self.account_data.cms.key_pair_id
            })

        request_headers = {}
        request_headers.update(self.api_headers)
        request_headers.update(headers)

        # Debug log for troubleshooting (only when debug_logging is enabled)
        auth_header = request_headers.get('Authorization', 'No Auth Header')
        utils.crunchy_log(f"make_request: {method} {url} | Auth: {auth_header[:50] + '...' if len(auth_header) > 50 else auth_header}", xbmc.LOGDEBUG)

        r = self.http.request(
            method,
            url,
            headers=request_headers,
            params=params,
            data=data,
            json=json_data
        )

        # something went wrong with authentication, possibly an expired token that wasn't caught above due to host
        # clock issues. set expiration date to 0 and re-call, triggering a full session refresh.
        if r.status_code == 401:
            if is_retry:
                raise LoginError('Request to API failed twice due to authentication issues.')

            utils.crunchy_log("make_request_proposal: request failed due to auth error", xbmc.LOGERROR)
            self.account_data.expires = date_to_str(get_date() - timedelta(seconds=1))
            return self.make_request(method, url, headers, params, data, json_data, True)

        utils.crunchy_log(f"make_request response: HTTP {r.status_code}", xbmc.LOGDEBUG)
        return get_json_from_response(r)

    def make_unauthenticated_request(
            self,
            method: str,
            url: str,
            headers=None,
            params=None,
            data=None,
            json_data=None,
    ) -> Optional[Dict]:
        """ Send a raw request without any session information """

        req = requests.Request(method, url, data=data, params=params, headers=headers, json=json_data)
        prepped = req.prepare()
        r = self.http.send(prepped)

        return get_json_from_response(r)

    def make_scraper_request(
            self,
            method: str,
            url: str,
            auth_type: str = "device",
            headers: Dict = None,
            params: Dict = None,
            data: Dict = None,
            json_data: Dict = None,
            timeout: int = 30,
            auto_refresh: bool = False,
            is_retry: bool = False
    ) -> Optional[Dict]:
        """
        Make HTTP request using CloudScraper for Cloudflare-protected endpoints.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            auth_type: Authorization type ("device", "legacy", "mobile", or None)
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
                    utils.crunchy_log("CRITICAL: Token expired but no refresh token available - session not properly initialized", xbmc.LOGERROR)
                    raise LoginError("Not authenticated - please restart plugin and login")

                self.refresh_attempts += 1

                if self.refresh_attempts > 3:
                    utils.crunchy_log("CRITICAL: Too many refresh attempts, stopping to prevent infinite loop", xbmc.LOGERROR)
                    raise LoginError("Authentication refresh failed repeatedly - please restart addon")

                utils.crunchy_log(f"Token refresh before scraper request (attempt {self.refresh_attempts}/3)", xbmc.LOGINFO)
                self._handle_refresh_flow()

        if self.account_data:
            params.update({
                "Policy": self.account_data.cms.policy,
                "Signature": self.account_data.cms.signature,
                "Key-Pair-Id": self.account_data.cms.key_pair_id
            })

        auth_headers = {}
        if auth_type == "device":
            auth_headers = {
                "Authorization": f"{G.api.account_data.token_type} {G.api.account_data.access_token}",
                "User-Agent": self.CRUNCHYROLL_UA_DEVICE,
            }
        elif auth_type == "legacy":
            auth_headers = {
                "Authorization": f"{G.api.account_data.token_type} {G.api.account_data.access_token}",
                "User-Agent": self.CRUNCHYROLL_UA,
            }
        elif auth_type == "mobile":
            auth_headers = {
                "Authorization": f"{G.api.account_data.token_type} {G.api.account_data.access_token}",
                "User-Agent": self.CRUNCHYROLL_UA_MOBILE,
            }

        request_headers = {}
        request_headers.update(auth_headers)
        request_headers.update(headers)

        scraper = self.create_auth_scraper()
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
                timeout=timeout
            )

            utils.crunchy_log(f"make_scraper_request response: HTTP {r.status_code}", xbmc.LOGDEBUG)

            if r.status_code == 401 and auto_refresh and not is_retry:
                utils.crunchy_log("Request failed due to auth error, forcing token refresh and retry", xbmc.LOGERROR)
                self.account_data.expires = date_to_str(get_date() - timedelta(seconds=1))
                return self.make_scraper_request(
                    method, url, auth_type, headers, params,
                    data, json_data, timeout, auto_refresh, is_retry=True
                )

            return get_json_from_response(r)

        except requests.exceptions.Timeout:
            utils.crunchy_log(f"CloudScraper request timeout: {url}", xbmc.LOGERROR)
            raise LoginError("Request timeout - check your network connection")
        except requests.exceptions.ConnectionError as e:
            utils.crunchy_log(f"CloudScraper connection error: {e}", xbmc.LOGERROR)
            raise LoginError("Network connection failed")
        except requests.exceptions.RequestException as e:
            utils.crunchy_log(f"CloudScraper request error: {e}", xbmc.LOGERROR)
            raise LoginError(f"Request failed: {str(e)}")
        except Exception as e:
            utils.crunchy_log(f"Unexpected CloudScraper error: {e}", xbmc.LOGERROR)
            raise LoginError(f"Unexpected error: {str(e)}")


def default_request_headers() -> Dict:
    return {
        "User-Agent": API.CRUNCHYROLL_UA,
        "Content-Type": "application/x-www-form-urlencoded"
    }


def get_date() -> datetime:
    return datetime.utcnow()


def date_to_str(date: datetime) -> str:
    return "{}-{}-{}T{}:{}:{}Z".format(
        date.year, date.month,
        date.day, date.hour,
        date.minute, date.second
    )


def str_to_date(string: str) -> datetime:
    time_format = "%Y-%m-%dT%H:%M:%SZ"

    try:
        res = datetime.strptime(string, time_format)
    except TypeError:
        res = datetime(*(time.strptime(string, time_format)[0:6]))

    return res


def get_json_from_response(r: Response) -> Optional[Dict]:
    from .utils import log_error_with_trace
    from .model import CrunchyrollError

    code: int = r.status_code
    response_type: str = r.headers.get("Content-Type")

    # no content - possibly POST/DELETE request?
    if not r or not r.text:
        try:
            r.raise_for_status()
            return None
        except HTTPError as e:
            # r.text is empty when status code cause raise
            r = e.response

    # handle text/plain response (e.g. fetch subtitle)
    if response_type == "text/plain":
        # if encoding is not provided in the response, Requests will make an educated guess and very likely fail
        # messing encoding up - which did cost me hours. We will always receive utf-8 from crunchy, so enforce that
        r.encoding = "utf-8"
        d = dict()
        d.update({
            'data': r.text
        })
        return d

    if not r.ok and r.text[0] != "{":
        raise CrunchyrollError(f"[{code}] {r.text}")

    try:
        r_json: Dict = r.json()
    except requests.exceptions.JSONDecodeError:
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
