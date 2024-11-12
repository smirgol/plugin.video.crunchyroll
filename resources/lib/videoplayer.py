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

import time
from typing import Optional
from urllib.parse import urlencode

import requests
import xbmc
import xbmcgui
import xbmcplugin

from resources.lib import utils
from resources.lib.globals import G
from resources.lib.gui import SkipModalDialog, show_modal_dialog
from resources.lib.model import Object, CrunchyrollError, LoginError
from resources.lib.videostream import VideoPlayerStreamData, VideoStream


class VideoPlayer(Object):
    """ Handles playing video using data contained in args object

    Keep instance of this class in scope, while playing, as threads started by it rely on it
    """

    def __init__(self):
        self._stream_data: VideoPlayerStreamData | None = None  # @todo: maybe rename prop and class?
        self._player: Optional[xbmc.Player] = xbmc.Player()  # @todo: what about garbage collection?
        self._skip_modal_duration_max = 10
        self.waitForStart = True
        self.lastUpdatePlayhead = 0
        self.clearedStream = False
        self.createTime = time.time()

    def start_playback(self):
        """ Set up player and start playback """

        # already playing for whatever reason?
        if self.isPlaying():
            utils.log("Skipping playback because already playing")
            return

        if not self._get_video_stream_data():
            return

        self._prepare_and_start_playback()

    def isPlaying(self) -> bool:
        if not self._stream_data:
            return False
        if self._player.isPlaying() and self._stream_data.stream_url == self._player.getPlayingFile():
                return True
        else:
            return False

    def isStartingOrPlaying(self) -> bool:
        """ Returns true if playback is running. Note that it also returns true when paused. """

        if not self._stream_data:
            return False

        if self.isPlaying():
            self.waitForStart = False
            return True

        # Wait max 20 sec for start playing the stream
        if (time.time() - self.createTime) > 20:
            if self.waitForStart:
                self.waitForStart = False
                utils.crunchy_log("Timout start playing file")
        return self.waitForStart

    def finished(self, forced=False):
        if not self.clearedStream or forced:
            self.clearedStream = True
            self.waitForStart = False
            self.clear_active_stream()

    def _get_video_stream_data(self) -> bool:
        """ Fetch all required stream data using VideoStream object """

        video_stream_helper = VideoStream()
        item = xbmcgui.ListItem(G.args.get_arg('title', 'Title not provided'))

        try:
            self._stream_data = video_stream_helper.get_player_stream_data()
            if not self._stream_data or not self._stream_data.stream_url:
                utils.crunchy_log("Failed to load stream info for playback", xbmc.LOGERROR)
                xbmcplugin.setResolvedUrl(int(G.args.argv[1]), False, item)
                xbmcgui.Dialog().ok(G.args.addon_name, G.args.addon.getLocalizedString(30064))
                return False

        except (CrunchyrollError, requests.exceptions.RequestException) as e:
            utils.log_error_with_trace("Failed to prepare stream info data", False)
            xbmcplugin.setResolvedUrl(int(G.args.argv[1]), False, item)

            # check for TOO_MANY_ACTIVE_STREAMS
            if 'TOO_MANY_ACTIVE_STREAMS' in str(e):
                xbmcgui.Dialog().ok(G.args.addon_name,
                                    G.args.addon.getLocalizedString(30080))
                playlist=xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                playlist.clear()
            else:
                xbmcgui.Dialog().ok(G.args.addon_name,
                                    G.args.addon.getLocalizedString(30064))
                playlist=xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
                playlist.clear()
            return False

        return True

    def _prepare_and_start_playback(self):
        """ Sets up the playback"""

        # prepare playback
        # note: when setting only a couple of values to the item, kodi will fetch the remaining from the url args
        #       since we do a full overwrite of the item with data from the cms object, which does not contain all
        #       wanted data - like playhead - we need to copy over that information to the PlayableItem before
        #        converting it to a kodi item. be aware of this.

        # copy playhead to PlayableItem (if resume is true on argv[3]) - this is required for resume capability
        if (
                self._stream_data.playable_item.playhead == 0
                and self._stream_data.playheads_data.get(G.args.get_arg('episode_id'), {})
                and G.args.argv[3] == 'resume:true'
        ):
            self._stream_data.playable_item.update_playcount_from_playhead(
                self._stream_data.playheads_data.get(G.args.get_arg('episode_id'))
            )

        item = self._stream_data.playable_item.to_item()
        item.setPath(self._stream_data.stream_url)
        item.setMimeType('application/dash+xml')
        item.setContentLookup(False)

        # inputstream adaptive
        from inputstreamhelper import Helper  # noqa

        is_helper = Helper("mpd", drm='com.widevine.alpha')
        if is_helper.check_inputstream():
            manifest_headers = {
                'User-Agent': G.api.CRUNCHYROLL_UA,
                'Authorization': f"Bearer {G.api.account_data.access_token}"
            }
            license_headers = {
                'User-Agent': G.api.CRUNCHYROLL_UA,
                'Content-Type': 'application/octet-stream',
                'Origin': 'https://static.crunchyroll.com',
                'Authorization': f"Bearer {G.api.account_data.access_token}",
                'x-cr-content-id': G.args.get_arg('episode_id'),
                'x-cr-video-token': self._stream_data.token
            }
            license_config = {
                'license_server_url': G.api.LICENSE_ENDPOINT,
                'headers': urlencode(license_headers),
                'post_data': 'R{SSM}',
                'response_data': 'JBlicense'
            }

            item.setProperty("inputstream", "inputstream.adaptive")
            item.setProperty("inputstream.adaptive.manifest_type", "mpd")
            item.setProperty("inputstream.adaptive.license_type", "com.widevine.alpha")
            item.setProperty('inputstream.adaptive.stream_headers', urlencode(manifest_headers))
            item.setProperty("inputstream.adaptive.manifest_headers", urlencode(manifest_headers))
            item.setProperty('inputstream.adaptive.license_key', '|'.join(list(license_config.values())))

            # @todo: i think other meta data like description and images are still fetched from args.
            #        we should call the objects endpoint and use this data to remove args dependency (besides id)

            # add soft subtitles url for configured language
            if self._stream_data.subtitle_urls:
                item.setSubtitles(self._stream_data.subtitle_urls)

            """ start playback"""
            xbmcplugin.setResolvedUrl(int(G.args.argv[1]), True, item)


    def update_playhead(self):
        """ background thread to update playback with crunchyroll in intervals """

        # store playtime of last update and compare before updating, so it won't update while e.g. pausing
        if (self.isPlaying() and
                (self._player.getTime() - self.lastUpdatePlayhead ) > 10
        ):
            self.lastUpdatePlayhead = self._player.getTime()
            # api request
            update_playhead(
                G.args.get_arg('episode_id'),
                int(self._player.getTime())
            )


    def check_skipping(self):
        """ background thread to check and handle skipping intro/credits/... """

        if len(self._stream_data.skip_events_data) == 0:
            return

        if not self.isPlaying():
            return

        for skip_type in list(self._stream_data.skip_events_data):
            # are we within the skip event timeframe?
            current_time = int(self._player.getTime())
            skip_time_start = self._stream_data.skip_events_data.get(skip_type).get('start')
            skip_time_end = self._stream_data.skip_events_data.get(skip_type).get('end')

            if skip_time_start <= current_time <= skip_time_end:
                self._ask_to_skip(skip_type)
                # remove the skip_type key from the data, so it won't trigger again
                self._stream_data.skip_events_data.pop(skip_type, None)


    def _ask_to_skip(self, section):
        """ Show skip modal """

        utils.crunchy_log("_ask_to_skip", xbmc.LOGINFO)

        dialog_duration = (self._stream_data.skip_events_data.get(section, []).get('end', 0) -
                           self._stream_data.skip_events_data.get(section, []).get('start', 0))

        # show only for the first X seconds
        dialog_duration = min(dialog_duration, self._skip_modal_duration_max)


        show_modal_dialog(SkipModalDialog, "plugin-video-crunchyroll-skip.xml",**{
                'seconds': dialog_duration,
                'seek_time': self._stream_data.skip_events_data.get(section).get('end'),
                'label': G.args.addon.getLocalizedString(30015),
                'addon_path': G.args.addon.getAddonInfo("path"),
                'content_id': G.args.get_arg('episode_id'),
            })

    def clear_active_stream(self):
        """ Tell Crunchyroll that we no longer use the stream.
            Crunchyroll keeps track of started streams. If they are not released, CR will block starting a new one.
        """

        if not G.args.get_arg('episode_id') or not self._stream_data.token:
            return

        try:
            G.api.make_request(
                method="DELETE",
                url=G.api.STREAMS_ENDPOINT_CLEAR_STREAM.format(G.args.get_arg('episode_id'), self._stream_data.token),
            )
        except (CrunchyrollError, LoginError, requests.exceptions.RequestException):
            # catch timeout or any other possible exception
            utils.crunchy_log("Failed to clear active stream for episode: %s" % G.args.get_arg('episode_id'))
            return

        utils.crunchy_log("Cleared active stream for episode: %s" % G.args.get_arg('episode_id'))


def update_playhead(content_id: str, playhead: int):
    """ Update playtime to Crunchyroll """

    # if sync_playtime is disabled in settings, do nothing
    if G.args.addon.getSetting("sync_playtime") != "true":
        return

    try:
        G.api.make_request(
            method="POST",
            url=G.api.PLAYHEADS_ENDPOINT.format(G.api.account_data.account_id),
            json_data={
                'playhead': playhead,
                'content_id': content_id
            },
            headers={
                'Content-Type': 'application/json'
            }
        )
    except (CrunchyrollError, requests.exceptions.RequestException) as e:
        # catch timeout or any other possible exception
        utils.crunchy_log(
            "Failed to update playhead to crunchyroll: %s for %s" % (
                str(e), content_id
            )
        )
        pass
