import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict
import requests

# Add resources/modules to path for cloudscraper
project_root = Path(__file__).parent.parent.parent
modules_path = project_root / "resources" / "modules"
if str(modules_path) not in sys.path:
    sys.path.insert(0, str(modules_path))


class TokenManager:
    """Manages access token with automatic refresh for integration tests"""

    TOKEN_ENDPOINT = "https://www.crunchyroll.com/auth/v1/token"
    AUTHORIZATION = "Basic cG84NzF4ZnN3YXNrdGI4ODlncnM6UFMtM3BXUmRoSHFNVFl3V21EUU1DODdQOHItN0NmOU4="
    USER_AGENT = "Crunchyroll/ANDROIDTV/3.54.3_22302 (Android 14; en-US; Chromecast)"

    def __init__(self, refresh_token: str, device_id: str):
        self.refresh_token = refresh_token
        self.device_id = device_id
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.account_id: Optional[str] = None

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
            "Content-Type": "application/x-www-form-urlencoded"
        }

        data = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
            "scope": "offline_access",
            "device_id": self.device_id,
            "device_name": "Kodi",
            "device_type": "MediaCenter"
        }

        response = scraper.post(
            self.TOKEN_ENDPOINT,
            headers=headers,
            data=data
        )

        if not response.ok:
            raise RuntimeError(
                f"Token refresh failed: {response.status_code} - {response.text}"
            )

        token_data = response.json()

        self.access_token = token_data["access_token"]
        self.refresh_token = token_data.get("refresh_token", self.refresh_token)

        expires_in = token_data.get("expires_in", 300)
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

        self.account_id = token_data.get("account_id")

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers with valid token"""
        return {
            "Authorization": f"Bearer {self.get_valid_token()}",
            "User-Agent": self.USER_AGENT
        }
