# Crunchyroll
# Copyright (C) 2018 MrKrabat
# Copyright (C) 2023 smirgol
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

"""Minimal HTTP proxy to bypass Cloudflare for Kodi manifest access.

Extracted from videostream.py so stream resolution and proxy concerns are
separate.  Dependencies are injected at construction time; the handler reads
from the owner instance instead of any global state.
"""

import http.server
import socketserver
import threading
import time
import urllib.parse

import xbmc

from ..modules import cloudscraper
from .utils.logging import crunchy_log


class CloudflareProxy:
    """Minimal HTTP proxy to bypass Cloudflare for Kodi manifest access.

    Auto-terminates after TTL to prevent zombie processes.
    """

    def __init__(
        self,
        user_agent: str,
        auth_token: str,
        token_type: str = "Bearer",
        ttl_seconds=30,
    ):
        self.server = None
        self.server_thread = None
        self.port = None
        self.ttl_seconds = ttl_seconds
        self.start_time = None
        self.shutdown_timer = None
        self.user_agent = user_agent
        self.auth_token = auth_token
        self.token_type = token_type

    def get_proxied_url(self, original_url: str) -> str:
        """Get proxied URL for Cloudflare-protected manifest."""
        try:
            if not self.server:
                self._start_server()

            # Verify server is still running
            if self.server_thread and not self.server_thread.is_alive():
                crunchy_log("Proxy server thread died, restarting", xbmc.LOGDEBUG)
                self.restart()

            # Encode original URL as parameter
            encoded_url = urllib.parse.quote(original_url, safe="")
            return f"http://127.0.0.1:{self.port}/proxy?url={encoded_url}"

        except Exception as e:
            crunchy_log(f"Error in get_proxied_url: {e}")
            # Try to restart proxy and return original URL as fallback
            try:
                self.restart()
                encoded_url = urllib.parse.quote(original_url, safe="")
                return f"http://127.0.0.1:{self.port}/proxy?url={encoded_url}"
            except Exception as restart_error:
                crunchy_log(f"Proxy restart failed: {restart_error}")
                return original_url  # Fallback to original URL

    def _start_server(self):
        """Start minimal HTTP server for manifest proxying with auto-shutdown."""
        try:
            owner = self

            class ProxyHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path.startswith("/proxy?url="):
                        # Extract original URL
                        url_param = self.path.split("url=", 1)[1]
                        original_url = urllib.parse.unquote(url_param)

                        crunchy_log(f"Proxy request for: {original_url}")

                        try:
                            # Use CloudScraper to fetch manifest
                            scraper = cloudscraper.create_scraper(
                                delay=10,
                                browser={"custom": self.server.owner.user_agent},
                            )

                            headers = {
                                "Authorization": f"{self.server.owner.token_type} {self.server.owner.auth_token}",
                                "User-Agent": self.server.owner.user_agent,
                            }

                            response = scraper.get(original_url, headers=headers, timeout=30)

                            if response.ok:
                                # Forward response to Kodi
                                self.send_response(200)
                                self.send_header(
                                    "Content-Type", response.headers.get("Content-Type", "application/dash+xml")
                                )
                                self.send_header("Content-Length", str(len(response.content)))
                                self.end_headers()
                                self.wfile.write(response.content)
                                crunchy_log(f"Proxy served: {len(response.content)} bytes", xbmc.LOGDEBUG)
                            else:
                                self.send_error(response.status_code, f"Upstream error: {response.status_code}")

                        except Exception as e:
                            crunchy_log(f"Proxy error: {e}")
                            self.send_error(500, f"Proxy error: {str(e)}")
                    else:
                        self.send_error(404, "Not found")

                def log_message(self, format, *args):
                    # Suppress default HTTP server logging
                    pass

            # Start server on random port
            self.server = socketserver.TCPServer(("127.0.0.1", 0), ProxyHandler)
            self.server.owner = owner
            self.port = self.server.server_address[1]

            # Start in background thread
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()

            # Set start time and schedule auto-shutdown
            self.start_time = time.time()
            self._schedule_auto_shutdown()

            crunchy_log(f"CloudFlare proxy started on port {self.port} (TTL: {self.ttl_seconds}s)")

        except Exception as e:
            crunchy_log(f"Failed to start CloudFlare proxy: {e}")
            raise

    def stop(self):
        """Stop proxy server."""
        # Cancel auto-shutdown timer
        if self.shutdown_timer:
            self.shutdown_timer.cancel()
            self.shutdown_timer = None

        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
            self.server_thread = None
            self.port = None
            self.start_time = None
            crunchy_log("CloudFlare proxy stopped")

    def restart(self):
        """Restart proxy server if it fails."""
        crunchy_log("Restarting CloudFlare proxy")
        self.stop()
        self._start_server()

    def _schedule_auto_shutdown(self):
        """Schedule automatic shutdown after TTL."""

        def auto_shutdown():
            if self.server:  # Check if still running
                crunchy_log(f"CloudFlare proxy auto-shutdown after {self.ttl_seconds}s TTL")
                self.stop()

        self.shutdown_timer = threading.Timer(self.ttl_seconds, auto_shutdown)
        self.shutdown_timer.daemon = True
        self.shutdown_timer.start()

    def extend_ttl(self, additional_seconds=30):
        """Extend proxy TTL if needed (for longer operations)."""
        if self.server and self.start_time:
            # Cancel current timer
            if self.shutdown_timer:
                self.shutdown_timer.cancel()

            crunchy_log(f"Extending proxy TTL by {additional_seconds}s", xbmc.LOGDEBUG)
            self.shutdown_timer = threading.Timer(additional_seconds, lambda: self.stop())
            self.shutdown_timer.daemon = True
            self.shutdown_timer.start()


# Global proxy instance (lazy loaded)
_cloudflare_proxy = None


def get_cloudflare_proxy(user_agent: str, auth_token: str, token_type: str = "Bearer") -> CloudflareProxy:
    """Get global CloudFlare proxy instance."""
    global _cloudflare_proxy
    if not _cloudflare_proxy:
        _cloudflare_proxy = CloudflareProxy(
            user_agent=user_agent,
            auth_token=auth_token,
            token_type=token_type,
        )
    return _cloudflare_proxy


def cleanup_cloudflare_proxy():
    """Cleanup global CloudFlare proxy instance."""
    global _cloudflare_proxy
    if _cloudflare_proxy:
        try:
            _cloudflare_proxy.stop()
            crunchy_log("CloudFlare proxy cleaned up", xbmc.LOGDEBUG)
        except Exception as e:
            crunchy_log(f"Error during proxy cleanup: {e}", xbmc.LOGDEBUG)
        finally:
            _cloudflare_proxy = None
