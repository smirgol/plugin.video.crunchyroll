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

    api.account_data = AccountData({
        "access_token": token,
        "refresh_token": test_credentials["refresh_token"],
        "device_id": test_credentials["device_id"],
        "account_id": test_credentials.get("account_id", "")
    })

    return api


@pytest.fixture(scope="session")
def clean_all_streams_before_suite(api_client):
    """Cleanup all active streams BEFORE test suite starts

    This prevents stream counter blocking from previous test runs.
    """
    try:
        active_streams = api_client.get_active_streams()
        if active_streams:
            print(f"\nCleaning {len(active_streams)} active streams before test suite...")
            for stream_info in active_streams:
                token = stream_info.get("token")
                content_id = stream_info.get("content_id")
                if token and content_id:
                    try:
                        api_client.clear_active_stream(token, content_id)
                    except Exception as e:
                        print(f"Warning: Failed to clear stream {content_id}: {e}")
    except Exception as e:
        print(f"Warning: Failed to cleanup streams: {e}")

    yield


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
            api_client.clear_active_stream(token, content_id)
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
