# -*- coding: utf-8 -*-
# Crunchyroll
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

from base64 import b64encode
from json import dumps

from resources.lib.model import Args, PlayableItem, SeriesData

from . import utils

def send_next_info(args: Args, current_episode: PlayableItem, next_episode: PlayableItem, play_url: str, notification_offset: int | None = None, series: SeriesData | None = None):
    """
    Notify next episode info to upnext.
    See https://github.com/im85288/service.upnext/wiki/Integration#sending-data-to-up-next for implementation details.
    """
    current = UpnextEpisode(current_episode, series)
    next = UpnextEpisode(next_episode, series)
    next_info = {
        "current_episode": current.__dict__,
        "next_episode": next.__dict__,
        "play_url": play_url,
    }
    if notification_offset is not None:
        next_info["notification_offset"] = notification_offset
    upnext_signal(args.addon_id, next_info)

class UpnextEpisode:
    def __init__(self, dto: PlayableItem, series_dto: SeriesData | None):
        self.episodeid: str | None = dto.episode_id
        self.tvshowid: str | None = dto.series_id
        self.title: str = dto.title_unformatted
        self.art: dict = {
            "thumb": dto.thumb,
        }
        if series_dto:
            self.art.update({
                # "tvshow.clearart": series_dto.clearart,
                # "tvshow.clearlogo": series_dto.clearlogo,
                "tvshow.fanart": series_dto.fanart,
                "tvshow.landscape": series_dto.fanart,
                "tvshow.poster": series_dto.poster,
            })
        self.season: int = dto.season
        self.episode: str = dto.episode
        self.showtitle: str = dto.tvshowtitle
        self.plot: str = dto.plot
        self.playcount: int = dto.playcount
        # self.rating: str = dto.rating
        self.firstaired: str = dto.year
        self.runtime: int = dto.duration

def upnext_signal(sender, next_info):
    """Send upnext_data to Kodi using JSON RPC"""
    data = [utils.to_unicode(b64encode(dumps(next_info).encode()))]
    utils.notify(sender=sender + '.SIGNAL', message='upnext_data', data=data)
