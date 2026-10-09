from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

from resources.lib.api import API
from resources.lib.auth import AUTHORIZATION, TOKEN_ENDPOINT

# Add resources/modules to path for cloudscraper
project_root = Path(__file__).parent.parent.parent
modules_path = project_root / "resources" / "modules"
if str(modules_path) not in sys.path:
    sys.path.insert(0, str(modules_path))


class TokenManager:
    """Manages access token with automatic refresh for integration tests"""

    # Reuse the production constants so there is a single source of truth.
    # The auth constants (TOKEN_ENDPOINT, AUTHORIZATION) live in auth.py; the
    # AUTHORIZATION client credential rotates every few weeks - renew it in
    # auth.py and the tests pick it up automatically. CRUNCHYROLL_UA stays on API.
    TOKEN_ENDPOINT = TOKEN_ENDPOINT
    AUTHORIZATION = AUTHORIZATION
    USER_AGENT = API.CRUNCHYROLL_UA

    def __init__(self, refresh_token: str, device_id: str):
        self.refresh_token = refresh_token
        self.device_id = device_id
        self.access_token: str | None = None
        self.token_expires_at: datetime | None = None
        self.account_id: str | None = None

    def get_valid_token(self) -> str:
        """Get valid access token, refresh if needed"""
        if not self.access_token or self._expires_soon():
            self._refresh_access_token()

        return self.access_token

    def _expires_soon(self) -> bool:
        """Check if token expires in less than 60 seconds"""
        if not self.token_expires_at:
            return True
        return (self.token_expires_at - datetime.now()).total_seconds() < 60

    def _refresh_access_token(self) -> None:
        """Refresh access token using refresh_token"""
        try:
            import cloudscraper
            scraper = cloudscraper.create_scraper()
            print(f"Using CloudScraper from: {cloudscraper.__file__}")
        except Exception as e:
            print(f"CloudScraper failed: {e}, falling back to requests")
            scraper = requests.Session()

        headers = {
            "Authorization": self.AUTHORIZATION,
            "User-Agent": self.USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "scope": "offline_access",
            "device_id": self.device_id,
            "device_name": "Kodi",
            "device_type": "MediaCenter",
        }

        response = scraper.post(self.TOKEN_ENDPOINT, headers=headers, data=data)

        if not response.ok:
            raise RuntimeError(f"Token refresh failed: {response.status_code} - {response.text}")

        token_data = response.json()

        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)

        expires_in = token_data.get("expires_in", 300)
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

        self.account_id = token_data.get("account_id")

    def get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers with valid token"""
        return {
            "Authorization": f"Bearer {self.get_valid_token()}",
            "User-Agent": self.USER_AGENT,
        }
