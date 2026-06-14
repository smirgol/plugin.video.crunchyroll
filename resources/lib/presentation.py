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

"""
Presentation layer: converts domain models and info dicts into Kodi artifacts.

This module is intentionally free of the G singleton. Callers pass in every
runtime dependency (addon base URL, sync_playtime flag, current query args).
"""

from __future__ import annotations

import xbmcgui

from . import router

# keys allowed in xbmcgui.ListItem.setInfo("video", ...)
KODI_INFO_TYPES = [
    "count",
    "size",
    "date",
    "genre",
    "country",
    "year",
    "episode",
    "season",
    "sortepisode",
    "top250",
    "setid",
    "tracknumber",
    "rating",
    "userrating",
    "watched",
    "overlay",
    "cast",
    "castandrole",
    "director",
    "mpaa",
    "plot",
    "plotoutline",
    "title",
    "originaltitle",
    "sorttitle",
    "duration",
    "studio",
    "tagline",
    "writer",
    "tvshowtitle",
    "premiered",
    "status",
    "set",
    "setoverview",
    "tag",
    "imdbnumber",
    "code",
    "aired",
    "credits",
    "lastplayed",
    "album",
    "artist",
    "votes",
    "path",
    "trailer",
    "dateadded",
    "mediatype",
    "dbid",
]


def quote_value(value) -> str:
    try:
        from urllib import quote_plus
    except ImportError:
        from urllib.parse import quote_plus

    if not isinstance(value, str):
        value = str(value)
    return quote_plus(value)


# Those parameters will be bypassed to URL as additional query_parameters if found in build_url path_params
# Don't Use this, because it will break the local playcount system.
# For the local playcount to work, the url (with all args) needs to be identical in the list and the in the player.
WHITELIST_URL_ARGS: list[str] = []


def build_url(path_params: dict, addonurl: str, route_name: str | None = None) -> str:
    """Create a plugin URL from path params, without touching global state."""

    if route_name is None:
        path = router.build_path(path_params)
    else:
        path = router.create_path_from_route(route_name, path_params)
    if path is None:
        path = "/"

    extra = ""
    for key, value in path_params.items():
        if key in WHITELIST_URL_ARGS and value:
            extra = extra + "&" + key + "=" + quote_value(value)
    if len(extra) > 0:
        extra = "?" + extra[1:]

    return addonurl.rstrip("/") + path + extra


def make_info_label(info: dict, current_args: dict, sync_playtime: bool = False) -> dict:
    """Generate info_labels from a new info dict and the current query args."""

    info_labels = {}
    info_items = list(info.items())

    # copy new information from info
    for key, value in info_items:
        if value and key in KODI_INFO_TYPES:
            info_labels[key] = value

    # copy old information from args, but don't overwrite
    arg_items = list(current_args.items())
    for key, value in arg_items:
        if value and key in KODI_INFO_TYPES and key not in info_labels:
            info_labels[key] = value

    # only allow to overwrite the local playcount if we sync the playtime with the server
    if sync_playtime:
        if "playcount" in info:
            info_labels["playcount"] = info["playcount"]
        if "playcount" in current_args and "playcount" not in info_labels:
            info_labels["playcount"] = current_args["playcount"]

    return info_labels


def present_listable(listable, sync_playtime: bool = False) -> xbmcgui.ListItem:
    """Convert a ListableItem model into a Kodi ListItem."""

    info = listable.get_info()
    list_info = {key: info[key] for key in KODI_INFO_TYPES if key in info}

    if sync_playtime and hasattr(listable, "playcount"):
        list_info["playcount"] = listable.playcount

    li = xbmcgui.ListItem()
    li.setLabel(listable.title)

    if hasattr(listable, "duration"):
        li.setProperty("IsPlayable", "true")
        li.setProperty("TotalTime", str(float(listable.duration)))
        if hasattr(listable, "playcount") and listable.playcount == 0:
            if hasattr(listable, "playhead") and listable.playhead > 0:
                resume = int(listable.playhead / listable.duration * 100)
                if 5 <= resume <= 90:
                    li.setProperty("ResumeTime", str(float(listable.playhead)))

    li.setInfo("video", list_info)

    artworks = {}
    if listable.thumb is not None:
        artworks["thumb"] = listable.thumb
    if listable.poster is not None:
        artworks["poster"] = listable.poster
        artworks["banner"] = listable.poster
    if listable.fanart is not None:
        artworks["fanart"] = listable.fanart
    if listable.landscape is not None:
        artworks["landscape"] = listable.landscape
    if listable.clearart is not None:
        artworks["clearart"] = listable.clearart
    if listable.clearlogo is not None:
        artworks["clearlogo"] = listable.clearlogo
    li.setArt(artworks)

    return li
