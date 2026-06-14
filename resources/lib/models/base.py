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

import json
from abc import abstractmethod
from json import dumps
from typing import TYPE_CHECKING, Any

import xbmcgui
import xbmcvfs

if TYPE_CHECKING:
    import xbmcaddon


class Meta(type, metaclass=type("", (type,), {"__str__": lambda _: "~hi"})):
    def __str__(self):
        return f"<class 'crunchyroll_beta.types.{self.__name__}'>"


class Object(metaclass=Meta):
    @staticmethod
    def default(obj: Object):
        return {
            "_": obj.__class__.__name__,
            **{
                attr: (getattr(obj, attr))
                for attr in filter(lambda x: not x.startswith("_"), obj.__dict__)
                if getattr(obj, attr) is not None
            },
        }

    def __str__(self) -> str:
        return dumps(self, indent=4, default=Object.default, ensure_ascii=False)

    @staticmethod
    def _read(data: dict, *keys: str) -> Any:
        """Read a value by trying multiple keys in order.

        Serialization stores attributes under their attribute name, while API
        responses use different keys. Passing both keeps the storage round-trip
        symmetric for renamed fields.
        """
        for key in keys:
            if key in data:
                return data[key]
        return None


class Cacheable(Object):
    def __init__(self):
        pass

    @abstractmethod
    def get_cache_file_name(self) -> str:
        pass

    @staticmethod
    def get_storage_path(addon: xbmcaddon.Addon) -> str:
        """Get cookie file path"""
        profile_path = xbmcvfs.translatePath(addon.getAddonInfo("profile"))

        return profile_path

    def load_from_storage(self, addon: xbmcaddon.Addon) -> dict:
        storage_file = self.get_storage_path(addon) + self.get_cache_file_name()

        if not xbmcvfs.exists(storage_file):
            return {}

        with xbmcvfs.File(storage_file) as file:
            data = json.load(file)

        d = dict()
        d.update(data)

        return d

    def delete_storage(self, addon: xbmcaddon.Addon) -> None:
        storage_file = self.get_storage_path(addon) + self.get_cache_file_name()

        if not xbmcvfs.exists(storage_file):
            return None

        xbmcvfs.delete(storage_file)

    def write_to_storage(self, addon: xbmcaddon.Addon) -> bool:
        storage_file = self.get_storage_path(addon) + self.get_cache_file_name()

        # serialize (Object has a to_str serializer)
        json_string = str(self)

        with xbmcvfs.File(storage_file, "w") as file:
            result = file.write(json_string)

        return result


class ListableItem(Object):
    """Base object for all DataObjects below that can be displayed in a Kodi List View"""

    def __init__(self):
        super().__init__()
        # just a very few that all child classes have in common, so I can spare myself of using hasattr() and getattr()
        self.id: str | None = None
        self.series_id: str | None = None  # @todo: this is not present in all subclasses, move that
        self.season_id: str | None = None  # @todo: this is not present in all subclasses, move that
        self.title: str | None = None
        self.title_unformatted: str | None = None
        self.thumb: str | None = None
        self.landscape: str | None = None
        self.fanart: str | None = None
        self.poster: str | None = None
        self.banner: str | None = None
        self.clearlogo: str | None = None
        self.clearart: str | None = None

    @abstractmethod
    def get_info(self) -> dict:
        """return a dict with info to set on the kodi ListItem (filtered) and access some data"""

        pass

    def to_item(self, addon: xbmcaddon.Addon | None = None) -> xbmcgui.ListItem:
        """Convert ourselves to a Kodi ListItem via the presentation layer."""

        from resources.lib.presentation import present_listable

        sync_playtime = addon.getSetting("sync_playtime") == "true" if addon is not None else False
        return present_listable(self, sync_playtime=sync_playtime)

    def update_playcount_from_playhead(self, playhead_data: dict):
        from .content import EpisodeData, MovieData

        if not isinstance(self, (EpisodeData, MovieData)):
            return

        self.playhead = playhead_data.get("playhead")
        if playhead_data.get("fully_watched"):
            self.playcount = 1
        else:
            self.recalc_playcount()


class PlayableItem(ListableItem):
    """Intermediate base class for playable items"""

    def __init__(self):
        super().__init__()
        self.playhead: int = 0
        self.duration: int = 0
        self.playcount: int = 0

    @abstractmethod
    def get_info(self) -> dict:
        """return a dict with info to set on the kodi ListItem (filtered) and access some data"""

        pass
