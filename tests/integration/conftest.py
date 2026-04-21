import os
import time
import pytest
from pathlib import Path
from dotenv import load_dotenv

from tests.fixtures.token_manager import TokenManager
from resources.lib.api import API
from resources.lib.model import AccountData


env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)


@pytest.fixture(scope="session")
def test_credentials():
    """Load test credentials from .env file"""
    refresh_token = os.getenv("CRUNCHYROLL_REFRESH_TOKEN")
    device_id = os.getenv("CRUNCHYROLL_DEVICE_ID")
    account_id = os.getenv("CRUNCHYROLL_ACCOUNT_ID")
    test_episode_id = os.getenv("TEST_EPISODE_ID", "GRVNEX7VY")

    if not refresh_token or not device_id:
        pytest.skip(
            "Integration tests require CRUNCHYROLL_REFRESH_TOKEN and "
            "CRUNCHYROLL_DEVICE_ID in tests/.env file. "
            "See tests/.env.example for template."
        )

    return {
        "refresh_token": refresh_token,
        "device_id": device_id,
        "account_id": account_id,
        "test_episode_id": test_episode_id
    }


@pytest.fixture(scope="session")
def token_manager(test_credentials):
    """Session-scoped token manager for auto-refreshing tokens"""
    return TokenManager(
        refresh_token=test_credentials["refresh_token"],
        device_id=test_credentials["device_id"]
    )


@pytest.fixture(scope="session")
def api_client(token_manager, test_credentials):
    """Session-scoped API client with authentication"""
    api = API()

    token = token_manager.get_valid_token()
    expires_at = token_manager.token_expires_at
    expires_str = "{}-{}-{}T{}:{}:{}Z".format(
        expires_at.year, expires_at.month, expires_at.day,
        expires_at.hour, expires_at.minute, expires_at.second
    )

    api.account_data = AccountData({
        "access_token": token,
        "refresh_token": test_credentials["refresh_token"],
        "device_id": test_credentials["device_id"],
        "account_id": test_credentials.get("account_id", ""),
        "token_type": "Bearer",
        "user_agent_type": "device",
        "expires": expires_str
    })

    return api



@pytest.fixture
def stream_cleanup(api_client):
    """Auto-cleanup stream after individual test

    Usage:
        def test_stream(api_client, stream_cleanup):
            response = api_client.get_stream("episode_id")
            stream_cleanup(response.token, "episode_id")  # Register for cleanup
            # Test continues...
            # Cleanup happens automatically after test
    """
    cleanup_items = []

    def _register_cleanup(token: str, content_id: str):
        """Register stream for cleanup"""
        cleanup_items.append((token, content_id))

    yield _register_cleanup

    for token, content_id in cleanup_items:
        try:
            api_client.make_request(
                method="DELETE",
                url=api_client.STREAMS_ENDPOINT_CLEAR_STREAM.format(content_id, token)
            )
        except Exception as e:
            print(f"Warning: Failed to cleanup stream {content_id}: {e}")


@pytest.fixture(autouse=True, scope="function")
def rate_limit():
    """Add delay between integration tests to be API-friendly"""
    yield
    time.sleep(1)


@pytest.fixture(scope="session")
def test_episode_id(test_credentials):
    """Fixed test episode ID for consistent streaming tests"""
    return test_credentials["test_episode_id"]
