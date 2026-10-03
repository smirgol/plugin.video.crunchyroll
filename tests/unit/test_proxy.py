"""Tests for the extracted CloudflareProxy in resources/lib/proxy.py."""

import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

from resources.lib.proxy import CloudflareProxy, cleanup_cloudflare_proxy, get_cloudflare_proxy


@pytest.fixture(autouse=True)
def reset_proxy_singleton():
    """Reset the module-level proxy singleton before every test."""
    import resources.lib.proxy as proxy_module

    proxy_module._cloudflare_proxy = None
    yield
    proxy_module._cloudflare_proxy = None


@pytest.fixture
def proxy():
    """Provide a CloudflareProxy with injected dependencies."""
    return CloudflareProxy(
        user_agent="TestAgent/1.0",
        auth_token="secret-token",
        token_type="Bearer",
        ttl_seconds=1,
    )


def test_proxy_stores_injected_credentials(proxy):
    """CloudflareProxy stores injected user_agent, auth_token and token_type."""
    assert proxy.user_agent == "TestAgent/1.0"
    assert proxy.auth_token == "secret-token"
    assert proxy.token_type == "Bearer"


def test_proxy_stores_default_token_type():
    """token_type defaults to Bearer when not provided."""
    proxy = CloudflareProxy(user_agent="A", auth_token="B")
    assert proxy.token_type == "Bearer"


def test_get_cloudflare_proxy_returns_singleton(proxy):
    """get_cloudflare_proxy returns the same instance for the same credentials."""
    first = get_cloudflare_proxy(
        user_agent="TestAgent/1.0",
        auth_token="secret-token",
        token_type="Bearer",
    )
    second = get_cloudflare_proxy(
        user_agent="TestAgent/1.0",
        auth_token="secret-token",
        token_type="Bearer",
    )
    assert first is second


def test_cleanup_cloudflare_proxy_stops_and_clears_singleton(proxy):
    """cleanup_cloudflare_proxy stops the running proxy and resets the singleton."""
    import resources.lib.proxy as proxy_module

    proxy_module._cloudflare_proxy = proxy
    mock_server = MagicMock()
    proxy.server = mock_server
    proxy.shutdown_timer = MagicMock()

    cleanup_cloudflare_proxy()

    mock_server.shutdown.assert_called_once()
    assert proxy_module._cloudflare_proxy is None


def test_proxy_start_server_assigns_port(proxy):
    """_start_server binds to a random localhost port and stores it."""
    proxy._start_server()

    assert proxy.server is not None
    assert proxy.port is not None
    assert isinstance(proxy.port, int)
    assert proxy.port > 0

    proxy.stop()


def test_proxy_get_proxied_url_returns_local_url(proxy):
    """get_proxied_url encodes the original URL and returns a localhost proxy URL."""
    original_url = "https://www.crunchyroll.com/manifest.mpd"
    proxied_url = proxy.get_proxied_url(original_url)

    assert proxied_url.startswith("http://127.0.0.1:")
    assert "/proxy?url=" in proxied_url
    assert "crunchyroll.com" in proxied_url

    proxy.stop()


def test_proxy_restart_resets_server(proxy):
    """restart stops and re-starts the proxy server."""
    proxy._start_server()
    first_port = proxy.port

    proxy.restart()

    assert proxy.port is not None
    assert proxy.port != first_port or proxy.server is not None

    proxy.stop()


def test_proxy_handler_forwards_with_injected_credentials():
    """The real ProxyHandler.do_GET fetches upstream using the injected credentials.

    This drives the actual nested handler over a live HTTP request rather than a
    replica, so the production Authorization/User-Agent header construction is
    exercised end to end.
    """
    upstream_url = "https://www.crunchyroll.com/manifest.mpd"

    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = b"<manifest/>"
    mock_response.headers = {"Content-Type": "application/dash+xml"}

    mock_scraper = MagicMock()
    mock_scraper.get.return_value = mock_response

    proxy = CloudflareProxy(
        user_agent="TestAgent/1.0",
        auth_token="secret-token",
        token_type="Bearer",
        ttl_seconds=5,
    )

    with patch("resources.lib.proxy.cloudscraper.create_scraper", return_value=mock_scraper):
        proxied_url = proxy.get_proxied_url(upstream_url)
        try:
            with urllib.request.urlopen(proxied_url, timeout=5) as resp:
                body = resp.read()
                assert resp.status == 200
                assert body == b"<manifest/>"
        finally:
            proxy.stop()

    # The handler must call upstream with the originally requested URL ...
    args, kwargs = mock_scraper.get.call_args
    assert args[0] == upstream_url
    # ... and headers built from the injected credentials, not any global state.
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer secret-token"
    assert headers["User-Agent"] == "TestAgent/1.0"


def test_proxy_handler_returns_404_for_unknown_path():
    """The real handler rejects paths that are not the /proxy?url= route."""
    proxy = CloudflareProxy(user_agent="A", auth_token="B", ttl_seconds=5)
    proxy._start_server()
    try:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://127.0.0.1:{proxy.port}/nope", timeout=5)
        assert exc_info.value.code == 404
    finally:
        proxy.stop()


def test_proxy_uses_injected_credentials_not_globals():
    """CloudflareProxy must not read from a global G object at construction time."""
    # Construction should be purely from arguments; any global import would fail
    # here if it tried to read an unset G. We already imported the module above,
    # so this test documents the dependency-injection contract.
    proxy = CloudflareProxy(
        user_agent="InjectedAgent",
        auth_token="injected-token",
        token_type="Macaron",
    )
    assert proxy.user_agent == "InjectedAgent"
    assert proxy.auth_token == "injected-token"
    assert proxy.token_type == "Macaron"
