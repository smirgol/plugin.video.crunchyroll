# -*- coding: utf-8 -*-
# Crunchyroll
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
import asyncio
import datetime
import os
import sys
import threading
import http.server
import socketserver
import urllib.parse
import time
from typing import Union, Dict, Optional, Any

import requests
import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.globals import G
from resources.lib.model import Object, CrunchyrollError, PlayableItem
from resources.lib.utils import log_error_with_trace, crunchy_log, \
    get_playheads_from_api, get_cms_object_data_by_ids, get_listables_from_response
from ..modules import cloudscraper


def _make_cloudflare_request(url: str) -> Optional[Dict]:
    """
    Make CloudScraper request for AndroidTV streaming endpoint

    Args:
        url: Stream URL that requires CloudFlare bypass

    Returns:
        JSON response dict or None if failed
    """
    try:
        # Create CloudScraper with AndroidTV User-Agent
        scraper = cloudscraper.create_scraper(
            delay=10,
            browser={'custom': G.api.CRUNCHYROLL_UA_DEVICE}
        )

        # Prepare headers with authentication
        headers = {
            "Authorization": f"{G.api.account_data.token_type} {G.api.account_data.access_token}",
            "User-Agent": G.api.CRUNCHYROLL_UA_DEVICE,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        # Add CMS parameters
        params = {
            "Policy": G.api.account_data.cms.policy,
            "Signature": G.api.account_data.cms.signature,
            "Key-Pair-Id": G.api.account_data.cms.key_pair_id
        }

        crunchy_log(f"CloudScraper request to: {url}")
        crunchy_log(f"CloudScraper User-Agent: {headers['User-Agent']}", xbmc.LOGDEBUG)

        response = scraper.get(
            url=url,
            headers=headers,
            params=params,
            timeout=30
        )

        crunchy_log(f"CloudScraper response: HTTP {response.status_code}", xbmc.LOGDEBUG)

        if response.ok:
            return response.json()
        else:
            crunchy_log(f"CloudScraper request failed: {response.status_code} {response.text}")
            return None

    except Exception as e:
        crunchy_log(f"CloudScraper request error: {e}")
        return None


class CloudflareProxy:
    """
    Minimal HTTP proxy to bypass Cloudflare for Kodi manifest access

    Auto-terminates after TTL to prevent zombie processes
    """

    def __init__(self, ttl_seconds=30):
        self.server = None
        self.server_thread = None
        self.port = None
        self.ttl_seconds = ttl_seconds
        self.start_time = None
        self.shutdown_timer = None

    def get_proxied_url(self, original_url: str) -> str:
        """Get proxied URL for Cloudflare-protected manifest"""
        try:
            if not self.server:
                self._start_server()

            # Verify server is still running
            if self.server_thread and not self.server_thread.is_alive():
                crunchy_log("Proxy server thread died, restarting", xbmc.LOGDEBUG)
                self.restart()

            # Encode original URL as parameter
            encoded_url = urllib.parse.quote(original_url, safe='')
            return f"http://127.0.0.1:{self.port}/proxy?url={encoded_url}"

        except Exception as e:
            crunchy_log(f"Error in get_proxied_url: {e}")
            # Try to restart proxy and return original URL as fallback
            try:
                self.restart()
                encoded_url = urllib.parse.quote(original_url, safe='')
                return f"http://127.0.0.1:{self.port}/proxy?url={encoded_url}"
            except Exception as restart_error:
                crunchy_log(f"Proxy restart failed: {restart_error}")
                return original_url  # Fallback to original URL

    def _start_server(self):
        """Start minimal HTTP server for manifest proxying with auto-shutdown"""
        try:
            class ProxyHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path.startswith('/proxy?url='):
                        # Extract original URL
                        url_param = self.path.split('url=', 1)[1]
                        original_url = urllib.parse.unquote(url_param)

                        crunchy_log(f"Proxy request for: {original_url}")

                        try:
                            # Use CloudScraper to fetch manifest
                            scraper = cloudscraper.create_scraper(
                                delay=10,
                                browser={'custom': G.api.CRUNCHYROLL_UA_DEVICE}
                            )

                            headers = {
                                "Authorization": f"{G.api.account_data.token_type} {G.api.account_data.access_token}",
                                "User-Agent": G.api.CRUNCHYROLL_UA_DEVICE,
                            }

                            response = scraper.get(original_url, headers=headers, timeout=30)

                            if response.ok:
                                # Forward response to Kodi
                                self.send_response(200)
                                self.send_header('Content-Type', response.headers.get('Content-Type', 'application/dash+xml'))
                                self.send_header('Content-Length', str(len(response.content)))
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
        """Stop proxy server"""
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
        """Restart proxy server if it fails"""
        crunchy_log("Restarting CloudFlare proxy")
        self.stop()
        self._start_server()

    def _schedule_auto_shutdown(self):
        """Schedule automatic shutdown after TTL"""
        def auto_shutdown():
            if self.server:  # Check if still running
                crunchy_log(f"CloudFlare proxy auto-shutdown after {self.ttl_seconds}s TTL")
                self.stop()

        self.shutdown_timer = threading.Timer(self.ttl_seconds, auto_shutdown)
        self.shutdown_timer.daemon = True
        self.shutdown_timer.start()

    def extend_ttl(self, additional_seconds=30):
        """Extend proxy TTL if needed (for longer operations)"""
        if self.server and self.start_time:
            # Cancel current timer
            if self.shutdown_timer:
                self.shutdown_timer.cancel()

            # Calculate new TTL
            elapsed = time.time() - self.start_time
            new_ttl = elapsed + additional_seconds

            crunchy_log(f"Extending proxy TTL by {additional_seconds}s", xbmc.LOGDEBUG)
            self.shutdown_timer = threading.Timer(additional_seconds, lambda: self.stop())
            self.shutdown_timer.daemon = True
            self.shutdown_timer.start()


# Global proxy instance (lazy loaded)
_cloudflare_proxy = None


def get_cloudflare_proxy() -> CloudflareProxy:
    """Get global CloudFlare proxy instance"""
    global _cloudflare_proxy
    if not _cloudflare_proxy:
        _cloudflare_proxy = CloudflareProxy()
    return _cloudflare_proxy


def cleanup_cloudflare_proxy():
    """Cleanup global CloudFlare proxy instance"""
    global _cloudflare_proxy
    if _cloudflare_proxy:
        try:
            _cloudflare_proxy.stop()
            crunchy_log("CloudFlare proxy cleaned up", xbmc.LOGDEBUG)
        except Exception as e:
            crunchy_log(f"Error during proxy cleanup: {e}", xbmc.LOGDEBUG)
        finally:
            _cloudflare_proxy = None


class VideoPlayerStreamData(Object):
    """ DTO to hold all relevant data for playback """

    def __init__(self):
        self.stream_url: str | None = None
        self.subtitle_urls: list[str] | None = None
        self.skip_events_data: Dict = {}
        self.playheads_data: Dict = {}
        # PlayableItem which is about to be played, that contains cms object data
        self.playable_item: PlayableItem | None = None
        # PlayableItem which contains cms obj data of playable_item's parent, if exists (Episodes, not Movies). currently not used.
        self.playable_item_parent: PlayableItem | None = None
        self.token: str | None = None
        self.next_playable_item: PlayableItem | None = None
        self.end_marker: str = "off"
        self.end_timecode: int | None = None


class VideoStream(Object):
    """ Build a VideoPlayerStreamData DTO using args.stream_id

    Will download stream details from cr api and store the appropriate stream url

    It will then check if soft subs are enabled in settings and if so, manage downloading the required subtitles, which
    are then renamed to make kodi label them in a readable way - this is because kodi uses the filename of the subtitles
    to identify the language and the cr files have cryptic filenames, which will render gibberish to the user on kodi
    instead of a proper label

    Finally, it will download any existing skip info, which can be used to skip intros / credits / summaries
    """

    def __init__(self, ):
        self.cache_expiration_time: int = 60 * 60 * 24 * 7  # 7 days
        # cache cleanup
        self._clean_cache_subtitles()

    def get_player_stream_data(self) -> Optional[VideoPlayerStreamData]:
        """ retrieve a VideoPlayerStreamData containing stream url + subtitle urls for playback """

        if not G.args.get_arg('stream_id'):
            return None

        video_player_stream_data = VideoPlayerStreamData()

        crunchy_log("VideoStream: Starting to retrieve data async")
        async_data = asyncio.run(self._gather_async_data())
        crunchy_log("VideoStream: Finished to retrieve data async")

        api_stream_data = async_data.get('stream_data')
        if not api_stream_data:
            raise CrunchyrollError("Failed to fetch stream data from api")

        video_player_stream_data.stream_url = self._get_stream_url_from_api_data_v2(async_data.get('stream_data'))
        video_player_stream_data.subtitle_urls = self._get_subtitles_from_api_data(async_data.get('stream_data'))
        video_player_stream_data.token = async_data.get('stream_data').get('token')

        video_player_stream_data.skip_events_data = async_data.get('skip_events_data')
        video_player_stream_data.playheads_data = async_data.get('playheads_data')
        video_player_stream_data.playable_item = async_data.get('playable_item')
        video_player_stream_data.playable_item_parent = async_data.get('playable_item_parent')
        video_player_stream_data.next_playable_item = async_data.get('next_playable_item')

        video_end = self._compute_when_episode_ends(video_player_stream_data)

        video_player_stream_data.end_marker = video_end.get('marker')
        video_player_stream_data.end_timecode = video_end.get('timecode')

        return video_player_stream_data

    async def _gather_async_data(self) -> Dict[str, Any]:
        """ gather data asynchronously and return them as a dictionary """

        episode_id = G.args.get_arg('episode_id')
        series_id = G.args.get_arg('series_id')

        # create threads
        # actually not sure if this works, as the requests lib is not async
        # also not sure if this is thread safe in any way, what if session is timed-out when starting this?
        t_stream_data = asyncio.create_task(self._get_stream_data_from_api())
        t_skip_events_data = asyncio.create_task(self._get_skip_events(episode_id))
        t_playheads = asyncio.create_task(get_playheads_from_api(episode_id))
        t_item_data = asyncio.create_task(get_cms_object_data_by_ids([episode_id, series_id]))
        t_upnext_data = asyncio.create_task(self._get_upnext_episode(episode_id))

        # start async requests and fetch results
        results = await asyncio.gather(t_stream_data, t_skip_events_data, t_playheads, t_item_data, t_upnext_data)

        listable_items = get_listables_from_response([value for key, value in results[3].items()]) if results[3] else []
        playable_items = [item for item in listable_items if item.id == episode_id]
        parent_listables = [item for item in listable_items if item.id == series_id]
        upnext_items = get_listables_from_response([results[4]]) if results[4] else None

        return {
            'stream_data': results[0] or {},
            'skip_events_data': results[1] or {},
            'playheads_data': results[2] or {},
            'playable_item': playable_items[0] if playable_items else None,
            'playable_item_parent': parent_listables[0] if parent_listables else None,
            'next_playable_item': upnext_items[0] if upnext_items else None,
        }

    @staticmethod
    async def _get_stream_data_from_api() -> Union[Dict, bool]:
        """ get json stream data from cr api for given args.stream_id using new endpoint b/c drm """

        # from utils import crunchy_log
        # Dynamic endpoint selection based on authentication type
        user_agent_type = getattr(G.api.account_data, 'user_agent_type', 'mobile')

        if user_agent_type == "device":
            # Use AndroidTV endpoint for device authentication
            stream_endpoint = G.api.STREAMS_ENDPOINT_DRM_ANDROID_TV
            crunchy_log("Using AndroidTV streaming endpoint for device session")
        else:
            # Use mobile/phone endpoint for legacy authentication
            stream_endpoint = G.api.STREAMS_ENDPOINT_DRM
            crunchy_log("Using mobile streaming endpoint for legacy session")

        stream_url = stream_endpoint.format(G.args.get_arg('episode_id'))
        crunchy_log("Stream URL: %s" % stream_url)
        crunchy_log(f"Current API User-Agent: {G.api.CRUNCHYROLL_UA}")
        crunchy_log(f"Current API Headers User-Agent: {G.api.api_headers.get('User-Agent', 'Unknown')}", xbmc.LOGDEBUG)

        # Use CloudScraper for AndroidTV endpoint (www.crunchyroll.com is Cloudflare protected)
        if user_agent_type == "device":
            crunchy_log("Using CloudScraper for AndroidTV streaming endpoint")
            req = _make_cloudflare_request(stream_url)
        else:
            crunchy_log("Using regular request for mobile streaming endpoint")
            req = G.api.make_request(
                method="GET",
                url=stream_url,
            )

        # check for error
        if "error" in req or req is None:
            item = xbmcgui.ListItem(G.args.get_arg('title', 'Title not provided'))
            xbmcplugin.setResolvedUrl(int(G.args.argv[1]), False, item)
            xbmcgui.Dialog().ok(G.args.addon_name, G.args.addon.getLocalizedString(30064))
            return False

        return req

    @staticmethod
    def _get_stream_url_from_api_data_v2(api_data: Dict) -> Union[str, None]:
        """ uses new endpoint to retrieve encryption data along with stream url """

        try:
            if G.args.addon.getSetting("soft_subtitles") == "false":
                url = api_data["hardSubs"]

                if G.args.subtitle in url:
                    url = url[G.args.subtitle]["url"]
                elif G.args.subtitle_fallback in url:
                    url = url[G.args.subtitle_fallback]["url"]
                else:
                    url = api_data["url"]
            else:
                url = api_data["url"]

            # Proxy Cloudflare-protected URLs for device authentication
            user_agent_type = getattr(G.api.account_data, 'user_agent_type', 'mobile')
            if user_agent_type == "device" and url and "www.crunchyroll.com" in url:
                proxy = get_cloudflare_proxy()
                proxied_url = proxy.get_proxied_url(url)
                crunchy_log(f"Proxying manifest URL: {url} -> {proxied_url}")
                url = proxied_url

        except IndexError:
            item = xbmcgui.ListItem(G.args.get_arg('title', 'Title not provided'))
            xbmcplugin.setResolvedUrl(int(G.args.argv[1]), False, item)
            xbmcgui.Dialog().ok(G.args.addon_name, G.args.addon.getLocalizedString(30064))
            return None

        return url

    def _get_subtitles_from_api_data(self, api_stream_data) -> Union[str, None]:
        """ retrieve appropriate subtitle urls from api data, using local caching and renaming """

        # we only need those urls if soft-subs are enabled in addon settings
        if G.args.addon.getSetting("soft_subtitles") == "false":
            return None

        subtitles_data_raw = []
        subtitles_url_cached = []

        if G.args.subtitle in api_stream_data["subtitles"]:
            subtitles_data_raw.append(api_stream_data.get("subtitles").get(G.args.subtitle))

        if G.args.subtitle_fallback and G.args.subtitle_fallback in api_stream_data["subtitles"]:
            subtitles_data_raw.append(api_stream_data.get("subtitles").get(G.args.subtitle_fallback))

        if not subtitles_data_raw:
            return None

        # we need to download the subtitles, cache and rename them to show proper labels in the kodi video player
        for subtitle_data in subtitles_data_raw:
            cache_result = self._get_subtitle_from_cache(
                subtitle_data.get('url', ""),
                subtitle_data.get('language', ""),
                subtitle_data.get('format', "")
            )

            if cache_result is not None:
                subtitles_url_cached.append(cache_result)

        return subtitles_url_cached if subtitles_url_cached is not None else None

    def _cache_subtitle(self, subtitle_url: str, subtitle_language: str, subtitle_format: str) -> bool:
        """ cache a subtitle from the given url and rename it for kodi to label it correctly """

        try:
            # api request streams
            subtitles_req = G.api.make_request(
                method="GET",
                url=subtitle_url
            )
        except Exception:
            log_error_with_trace("error in requesting subtitle data from api")
            raise CrunchyrollError(
                "Failed to download subtitle for language %s from url %s" % (subtitle_language, subtitle_url)
            )

        if not subtitles_req.get('data', None):
            # error
            raise CrunchyrollError("Returned data is not text")

        cache_target = xbmcvfs.translatePath(self.get_cache_path() + G.args.get_arg('stream_id') + '/')
        xbmcvfs.mkdirs(cache_target)

        cache_file = self.get_cache_file_name(subtitle_language, subtitle_format)

        with open(cache_target + cache_file, 'w', encoding='utf-8') as file:
            result = file.write(subtitles_req.get('data'))

        return True if result > 0 else False

    def _get_subtitle_from_cache(
            self,
            subtitle_url: str,
            subtitle_language: str,
            subtitle_format: str
    ) -> Union[str, None]:
        """ try to get a subtitle using its url, language info and format either from cache or api """

        if not subtitle_url or not subtitle_language or not subtitle_format:
            crunchy_log("get_subtitle_from_cache: missing argument", xbmc.LOGERROR)
            return None

        # prepare the filename for the subtitles
        cache_file = self.get_cache_file_name(subtitle_language, subtitle_format)

        # build full path to cached file
        cache_target = xbmcvfs.translatePath(self.get_cache_path() + G.args.get_arg('stream_id') + '/') + cache_file

        # check if cached file exists
        if not xbmcvfs.exists(cache_target):
            # download and cache file
            if not self._cache_subtitle(subtitle_url, subtitle_language, subtitle_format):
                # log error
                log_error_with_trace("Failed to write subtitle to cache")
                return None

        cache_file_url = ('special://userdata/addon_data/plugin.video.crunchyroll/cache_subtitles/' +
                          G.args.get_arg('stream_id') +
                          '/' + cache_file)

        return cache_file_url

    def _clean_cache_subtitles(self) -> bool:
        """ clean up all cached subtitles """

        expires = datetime.datetime.now() - datetime.timedelta(seconds=self.cache_expiration_time)

        cache_base_dir = self.get_cache_path()
        dirs, files = xbmcvfs.listdir(cache_base_dir)

        for cache_dir in dirs:
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(cache_base_dir, cache_dir)))
            if mtime < expires:
                crunchy_log("Cache dir %s is older than 7 days - removing" % os.path.join(cache_base_dir, cache_dir))
                xbmcvfs.rmdir(os.path.join(cache_base_dir, cache_dir) + '/', force=True)

        return True

    @staticmethod
    def get_cache_path() -> str:
        """ return base path for subtitles caching """

        return xbmcvfs.translatePath(G.args.addon.getAddonInfo("profile") + 'cache_subtitles/')

    @staticmethod
    def get_cache_file_name(subtitle_language: str, subtitle_format: str) -> str:
        """ build a file name for the subtitles file that kodi can display with a readable label """

        # kodi ignores the first part of e.g. de-DE - split and use only first part in uppercase
        iso_parts = subtitle_language.split('-')

        filename = xbmcvfs.makeLegalFilename(
            subtitle_language +
            '.' + iso_parts[0] +
            '.' + subtitle_format
        )

        # for some reason, makeLegalFilename likes to append a '/' at the end, effectively making the file a directory
        if filename.endswith('/'):
            filename = filename[:-1]

        # have to use filesystemencoding since filename contains non ascii characters in some language (such as french)
        # and kodi file system encoding can be set to ASCII
        return filename.encode(sys.getfilesystemencoding(), "ignore").decode(sys.getfilesystemencoding())

    @staticmethod
    async def _get_skip_events(episode_id) -> Optional[Dict]:
        """ fetch skip events data from api and return a prepared object for supported skip types if data is valid """

        # if none of the skip options are enabled in setting, don't fetch that data
        if (G.args.addon.getSetting("enable_skip_intro") != "true" and
                G.args.addon.getSetting("enable_skip_credits") != "true" and
                G.args.addon.getSetting("upnext_mode") == "disabled"):
            return None

        try:
            crunchy_log("Requesting skip data from %s" % G.api.SKIP_EVENTS_ENDPOINT.format(episode_id))

            # api request streams
            req = G.api.make_unauthenticated_request(
                method="GET",
                url=G.api.SKIP_EVENTS_ENDPOINT.format(episode_id)
            )
        except (requests.exceptions.RequestException, CrunchyrollError):
            try:
                # Some streams raise a 403 on SKIP_EVENTS endpoint but skip data are available in INTRO_V2 endpoint
                intro_req = G.api.make_unauthenticated_request(
                    method="GET",
                    url=G.api.INTRO_V2_ENDPOINT.format(episode_id)
                )
                req = {"intro": {
                    "start": intro_req.get("startTime"),
                    "end": intro_req.get("endTime"),
                }}
            except (requests.exceptions.RequestException, CrunchyrollError):
                # can be okay for e.g. movies, thus only log error, but don't show notification
                crunchy_log(
                    "_get_skip_events: error in requesting skip events data from api. possibly no data available",
                    False
                )
                return None

        if not req or "error" in req:
            crunchy_log("_get_skip_events: error in requesting skip events data from api (2)")
            return None

        # prepare the data a bit
        supported_skips = ['intro', 'credits', 'preview']
        prepared = dict()
        for skip_type in supported_skips:
            if req.get(skip_type) and req.get(skip_type).get('start') is not None and req.get(skip_type).get(
                    'end') is not None:
                prepared.update({
                    skip_type: dict(start=req.get(skip_type).get('start'), end=req.get(skip_type).get('end'))
                })
                crunchy_log("_get_skip_events: check for %s PASSED" % skip_type, xbmc.LOGINFO)
            else:
                crunchy_log("_get_skip_events: check for %s FAILED" % skip_type, xbmc.LOGINFO)

        if G.args.addon.getSetting("enable_skip_intro") != "true" and prepared.get('intro'):
            prepared.pop('intro', None)

        if G.args.addon.getSetting("enable_skip_credits") != "true" and prepared.get('credits'):
            prepared.pop('credits', None)
        return prepared if len(prepared) > 0 else None

    @staticmethod
    async def _get_upnext_episode(id: str) -> Optional[Dict]:
        """ fetch upnext episode data from api """

        # if upnext integration is disabled, don't fetch data
        if G.args.addon.getSetting("upnext_mode") == "disabled":
            return None

        try:
            req = G.api.make_request(
                method="GET",
                url=G.api.UPNEXT_ENDPOINT.format(id),
                params={
                    "locale": G.args.subtitle
                }
            )
        except (CrunchyrollError, requests.exceptions.RequestException) as e:
            crunchy_log("_get_upnext_episode: failed to load for: %s" % id)
            return None
        if not req or "error" in req or len(req.get("data", [])) == 0:
            return None

        return req.get("data")[0]

    @staticmethod
    def _compute_when_episode_ends(partial_stream_data: VideoPlayerStreamData) -> Dict[str, Any]:
        """ Extract timecode for video end from skip_events_data.

        Extracted timecode depends on *upnext_mode* user setting and available skip events data.
        upnext_mode can hold 4 different behaviour.
        - "disabled", so no need to compute anything.
        - "fixed", so we should send the timecode for the last 15s (user can change this duration by *upnext_fixed_duration* settings).
        - "preview", which means we have to retrieve preview timecode from skip event API.
           If preview timecode is not available, go back to the same behaviour as "fixed" mode.
        - "credits", which means we have to retrieve credits and preview timecode from skip event API.
           If credits timecode is not available, go back to the same behaviour as "preview" mode.
           Additionaly, we have to check there is no additional scenes after credits,
           so we check if preview starts at credits end. Otherwise, video end timecode will be the preview start timecode.
        """

        result = {
            'marker': 'off',
            'timecode': None
        }
        upnext_mode = G.args.addon.getSetting('upnext_mode')
        if upnext_mode == 'disabled' or not partial_stream_data.next_playable_item:
            return result

        video_end = partial_stream_data.playable_item.duration
        fixed_duration = int(G.args.addon.getSetting('upnext_fixed_duration'), 10)
        # Standard behaviour is to show upnext 15s before the end of the video
        result = {
            'marker': 'fixed',
            'timecode': video_end - fixed_duration
        }

        skip_events_data = partial_stream_data.skip_events_data
        # If upnext selected mode is fixed or there is no available skip data
        if upnext_mode == 'fixed' or not skip_events_data or (not skip_events_data.get('credits') and not skip_events_data.get('preview')):
            return result

        # Extract skip data
        credits_start = skip_events_data.get('credits', {}).get('start')
        credits_end = skip_events_data.get('credits', {}).get('end')
        preview_start = skip_events_data.get('preview', {}).get('start')
        preview_end = skip_events_data.get('preview', {}).get('end')

        # If there is no data about preview but credits ends less than 20s before the end, consider time after credits_end is the preview
        if not preview_start and credits_end and credits_end >= video_end - 20:
            preview_start = credits_end
            preview_end = video_end

        # If there are outro and preview
        # and if the outro ends when the preview start
        if upnext_mode == 'credits' and credits_start and credits_end and preview_start and credits_end + 3 > preview_start:
            result = {
                'marker': 'credits',
                'timecode': credits_start
            }
        # If there is a preview
        elif preview_start:
            result = {
                'marker': 'preview',
                'timecode': preview_start
            }

        return result
