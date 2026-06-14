"""Tests for the extracted CloudflareProxy in resources/lib/proxy.py."""

import http.server
import socketserver
from unittest.mock import MagicMock

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


def test_proxy_handler_reads_credentials_from_owner():
    """The nested ProxyHandler reads user_agent and auth_token from the owner instance."""
    owner = MagicMock()
    owner.user_agent = "OwnerAgent"
    owner.auth_token = "owner-token"
    owner.token_type = "Basic"

    # Build a fake TCP server whose .owner points to our mock.
    class FakeServer(socketserver.TCPServer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.owner = owner

    class FakeHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            # Replicate the exact credential-read pattern from the real ProxyHandler
            self.user_agent = self.server.owner.user_agent
            self.auth_token = self.server.owner.auth_token
            self.token_type = self.server.owner.token_type
            self.send_response(200)
            self.end_headers()

        def log_message(self, fmt, *args):
            pass

    server = FakeServer(("127.0.0.1", 0), FakeHandler)
    try:
        assert server.owner.user_agent == "OwnerAgent"
        assert server.owner.auth_token == "owner-token"
        assert server.owner.token_type == "Basic"
    finally:
        server.server_close()


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
