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

from __future__ import annotations

from .base import ListableItem, PlayableItem


class SeriesData(ListableItem):
    """A Series containing Seasons containing Episodes"""

    def __init__(self, data: dict):
        super().__init__()
        from .. import utils
        from ..utils.images import ImageType

        panel = data.get("panel") or data
        meta = panel.get("series_metadata") or panel

        self.id = panel.get("id")
        self.title: str = panel.get("title")
        self.title_unformatted: str = panel.get("title")
        self.tvshowtitle: str = panel.get("title")
        self.series_id: str | None = panel.get("id")
        self.season_id: str | None = None
        self.plot: str = panel.get("description", "")
        self.plotoutline: str = panel.get("description", "")
        self.year: str = str(meta.get("series_launch_year")) + "-01-01"
        self.aired: str = str(meta.get("series_launch_year")) + "-01-01"
        self.premiered: str = str(meta.get("series_launch_year"))
        self.episode: int = meta.get("episode_count")
        self.season: int = meta.get("season_count")

        self.thumb: str | None = utils.get_img_from_struct(panel, ImageType.POSTER_WIDE, 2)
        self.landscape: str | None = utils.get_img_from_struct(panel, ImageType.POSTER_WIDE, 2)
        self.fanart: str | None = utils.infer_img_from_id(self.id, ImageType.BACKDROP_WIDE)
        self.clearlogo: str | None = utils.infer_img_from_id(self.id, ImageType.TITLE_LOGO)
        self.clearart: str | None = utils.infer_img_from_id(self.id, ImageType.TITLE_LOGO)
        self.poster: str | None = utils.get_img_from_struct(panel, ImageType.POSTER_TALL, 2)
        self.banner: str | None = None
        self.rating: int = 0
        self.playcount: int = 0

    def recalc_playcount(self):
        # @todo: not sure how to get that without checking all child seasons and their episodes
        pass

    def get_info(self) -> dict:
        # in theory, we could also omit this method and just iterate over the objects properties and use them
        # to set data on the Kodi ListItem, but this way we are decoupled from their naming convention
        return {
            "title": self.title,
            "tvshowtitle": self.tvshowtitle,
            "season": self.season,
            "episode": self.episode,
            "plot": self.plot,
            "plotoutline": self.plotoutline,
            "playcount": self.playcount,
            "series_id": self.series_id,
            "year": self.year,
            "aired": self.aired,
            "premiered": self.premiered,
            "rating": self.rating,
            "mediatype": "season",
            # internally used for routing
            "mode": "seasons",
        }


class SeasonData(ListableItem):
    """A Season/Arc of a Series containing Episodes"""

    def __init__(self, data: dict):
        super().__init__()

        self.id = data.get("id")
        self.title: str = data.get("title")
        self.title_unformatted: str = data.get("title")
        self.tvshowtitle: str = data.get("title")
        self.series_id: str | None = data.get("series_id")
        self.season_id: str | None = data.get("id")
        self.plot: str = ""  # does not have description. maybe object endpoint?
        self.plotoutline: str = ""
        self.year: str = ""
        self.aired: str = ""
        self.premiered: str = ""
        self.episode: int = 0  # @todo we want to display that, but it's not in the data
        self.season: int = data.get("season_number")
        self.thumb: str | None = None
        self.landscape: str | None = None
        self.fanart: str | None = None
        self.poster: str | None = None
        self.banner: str | None = None
        self.clearlogo: str | None = None
        self.clearart: str | None = None
        self.rating: int = 0
        self.playcount: int = 1 if data.get("is_complete") else 0

        self.recalc_playcount()

    def recalc_playcount(self):
        # @todo: not sure how to get that without checking all child episodes
        pass

    def get_info(self) -> dict:
        return {
            "title": self.title,
            "tvshowtitle": self.tvshowtitle,
            "season": self.season,
            "episode": self.episode,
            # 'plot': self.plot,
            # 'plotoutline': self.plotoutline,
            "playcount": self.playcount,
            "series_id": self.series_id,
            "season_id": self.season_id,
            # 'year': self.year,
            # 'aired': self.aired,
            # 'premiered': self.premiered,
            "rating": self.rating,
            "mediatype": "season",
            # internally used for routing
            "mode": "episodes",
        }


# dto
class EpisodeData(PlayableItem):
    """A single Episode of a Season of a Series"""

    def __init__(self, data: dict):
        super().__init__()
        from .. import utils
        from ..utils.images import ImageType

        panel = data.get("panel") or data
        meta = panel.get("episode_metadata") or panel

        self.id = panel.get("id")
        self.title: str = utils.format_long_episode_title(
            meta.get("series_title"), meta.get("season_number", 1), meta.get("episode_number"), panel.get("title")
        )
        self.title_unformatted: str = panel.get("title")
        self.tvshowtitle: str = meta.get("series_title", "")
        self.duration: int = int(meta.get("duration_ms", 0) / 1000)
        self.playhead: int = data.get("playhead", 0)
        self.season: int = meta.get("season_number", 1)
        self.episode: int = meta.get("episode_number", 1)
        self.episode_id: str | None = panel.get("id")
        self.season_id: str | None = meta.get("season_id")
        self.series_id: str | None = meta.get("series_id")
        self.plot: str = panel.get("description", "")
        self.plotoutline: str = panel.get("description", "")
        self.year: str = meta.get("episode_air_date")[:4] if meta.get("episode_air_date") is not None else ""
        self.aired: str = meta.get("episode_air_date")[:10] if meta.get("episode_air_date") is not None else ""
        self.premiered: str = meta.get("episode_air_date")[:10] if meta.get("episode_air_date") is not None else ""
        self.thumb: str | None = utils.get_img_from_struct(panel, ImageType.THUMBNAIL, 2)
        self.landscape: str | None = utils.get_img_from_struct(panel, ImageType.THUMBNAIL, 2)
        self.fanart: str | None = utils.get_img_from_struct(panel, ImageType.THUMBNAIL, 2)
        self.poster: str | None = None
        self.banner: str | None = None
        self.clearlogo: str | None = None
        self.clearart: str | None = None
        self.rating: int = 0
        self.playcount: int = 0
        self.stream_id: str | None = utils.get_stream_id_from_item(panel)

        self.recalc_playcount()

    def recalc_playcount(self):
        if self.playhead is not None and self.duration is not None:
            self.playcount = 1 if (int(self.playhead / self.duration * 100)) > 90 else 0

    def get_info(self) -> dict:
        return {
            "title": self.title,
            "tvshowtitle": self.tvshowtitle,
            "season": self.season,
            "episode": self.episode,
            "plot": self.plot,
            "plotoutline": self.plotoutline,
            "playhead": self.playhead,
            "duration": self.duration,
            "playcount": self.playcount,
            "season_id": self.season_id,
            "series_id": self.series_id,
            "episode_id": self.episode_id,
            "stream_id": self.stream_id,
            "year": self.year,
            "aired": self.aired,
            "premiered": self.premiered,
            "rating": self.rating,
            "mediatype": "episode",
            # internally used for routing
            "mode": "videoplay",
        }


class MovieData(PlayableItem):
    def __init__(self, data: dict):
        super().__init__()
        from .. import utils
        from ..utils.images import ImageType

        panel = data.get("panel") or data
        meta = panel.get("movie_metadata") or panel

        self.id = panel.get("id")
        self.title: str = meta.get("movie_listing_title", "")
        self.title_unformatted: str = meta.get("movie_listing_title", "")
        self.tvshowtitle: str = meta.get("movie_listing_title", "")
        self.duration: int = int(meta.get("duration_ms", 0) / 1000)
        self.playhead: int = data.get("playhead", 0)
        self.season: int = 1
        self.episode: int = 1
        self.episode_id: str | None = panel.get("id")
        self.season_id: str | None = None
        self.series_id: str | None = None
        self.plot: str = panel.get("description", "")
        self.plotoutline: str = panel.get("description", "")
        self.year: str = (
            meta.get("premium_available_date")[:10] if meta.get("premium_available_date") is not None else ""
        )
        self.aired: str = (
            meta.get("premium_available_date")[:10] if meta.get("premium_available_date") is not None else ""
        )
        self.premiered: str = (
            meta.get("premium_available_date")[:10] if meta.get("premium_available_date") is not None else ""
        )
        self.thumb: str | None = utils.get_img_from_struct(panel, ImageType.THUMBNAIL, 2)
        self.landscape: str | None = utils.get_img_from_struct(panel, ImageType.THUMBNAIL, 2)
        self.fanart: str | None = utils.get_img_from_struct(panel, ImageType.THUMBNAIL, 2)
        self.poster: str | None = None
        self.banner: str | None = None
        self.clearlogo: str | None = None
        self.clearart: str | None = None
        self.rating: int = 0
        self.playcount: int = 0
        self.stream_id: str | None = utils.get_stream_id_from_item(panel)

        self.recalc_playcount()

    def recalc_playcount(self):
        if self.playhead is not None and self.duration is not None:
            self.playcount = 1 if (int(self.playhead / self.duration * 100)) > 90 else 0

    def get_info(self) -> dict:
        return {
            "title": self.title,
            "tvshowtitle": self.tvshowtitle,
            "season": self.season,
            "episode": self.episode,
            "plot": self.plot,
            "plotoutline": self.plotoutline,
            "playhead": self.playhead,
            "duration": self.duration,
            "playcount": self.playcount,
            "series_id": self.series_id,
            "season_id": self.season_id,
            "episode_id": self.episode_id,
            "stream_id": self.stream_id,
            "year": self.year,
            "aired": self.aired,
            "premiered": self.premiered,
            "rating": self.rating,
            "mediatype": "movie",
            # internally used for routing
            "mode": "videoplay",
        }
