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
import re
from typing import TYPE_CHECKING

import requests
import xbmc

from ..model import CrunchyrollError, EpisodeData, ListableItem, MovieData, SeasonData, SeriesData

if TYPE_CHECKING:
    from xbmcgui import ListItem




def get_listables_from_response(
    data: list[dict],
    item_type_hint: str | None = None,
    args=None,
) -> list[ListableItem]:
    """takes an API response object, determines type of its contents and creates DTOs for further processing

    For mixed lists (browse, search, watchlist) the type is detected per item. The newer content/v2 endpoints
    (seasons, episodes) no longer carry a type identifier, so the caller passes the known type via item_type_hint.
    """
    from . import filters, logging

    listable_items = []

    for item in data:
        item_type = item.get("panel", {}).get("type") or item.get("type") or item.get("__class__") or item_type_hint
        if not item_type:
            logging.crunchy_log(
                f"get_listables_from_response | failed to determine type for response item "
                f"{json.dumps(item, indent=4)}",
                xbmc.LOGERROR,
            )
            continue

        if item_type == "series":
            if not filters.filter_series(item, args=args):
                continue
            listable_items.append(SeriesData(item))
        elif item_type == "season":
            if not filters.filter_seasons(item, args=args):
                continue
            listable_items.append(SeasonData(item))
        elif item_type == "episode":
            listable_items.append(EpisodeData(item))
        elif item_type == "movie":
            listable_items.append(MovieData(item))
        else:
            logging.crunchy_log(
                f"get_listables_from_response | unhandled index for metadata. {json.dumps(item, indent=4)}",
                xbmc.LOGERROR,
            )
            continue

    return listable_items


async def get_cms_object_data_by_ids(ids: list, api, args) -> dict:
    """fetch info from api object endpoint for given ids. Useful to complement missing data"""


    ids_filtered = [item for item in ids if item != 0 and item is not None]
    if len(ids_filtered) == 0:
        return {}

    try:
        req = api.make_request(
            method="GET",
            url=api.OBJECTS_BY_ID_LIST_ENDPOINT.format(",".join(ids_filtered)),
            params={
                "locale": args.subtitle,
                "ratings": "true",
            },
        )
    except (CrunchyrollError, requests.exceptions.RequestException):
        from . import logging
        logging.crunchy_log(f"get_cms_object_data_by_ids: failed to load for: {','.join(ids_filtered)}")
        return {}

    if not req or "error" in req:
        return {}

    return {item.get("id"): item for item in req.get("data")}


def get_stream_id_from_item(item: dict) -> str | None:
    """takes a URL string and extracts the stream ID from it"""

    pattern = "/videos/([^/]+)/streams"
    stream_id = re.search(pattern, item.get("__links__", {}).get("streams", {}).get("href", ""))
    if not stream_id:
        stream_id = re.search(pattern, item.get("streams_link", ""))

    if not stream_id:
        raise CrunchyrollError("Failed to get stream id")

    return stream_id[1]


async def get_playheads_from_api(episode_ids: str | list, api, args) -> dict:
    """Retrieve playhead data from API for given episode / movie ids"""


    if isinstance(episode_ids, str):
        episode_ids = [episode_ids]

    response = api.make_scraper_request(
        method="GET",
        url=api.PLAYHEADS_ENDPOINT.format(api.account_data.account_id),
        params={
            "locale": args.subtitle,
            "preferred_audio_language": api.account_data.default_audio_language,
            "content_ids": ",".join(episode_ids),
        },
        auto_refresh=True,
    )

    out = {}

    if not response:
        return out

    for item in response.get("data"):
        out[item.get("content_id")] = {
            "playhead": item.get("playhead"),
            "fully_watched": item.get("fully_watched"),
        }

    return out


async def get_watchlist_status_from_api(ids: list, api, args) -> list:
    """retrieve watchlist status for given media ids"""
    from . import logging


    req = api.make_scraper_request(
        method="GET",
        url=api.WATCHLIST_V2_ENDPOINT.format(api.account_data.account_id),
        params={
            "content_ids": ",".join(ids),
            "locale": args.subtitle,
        },
        auto_refresh=True,
    )

    if not req or req.get("error") is not None:
        logging.crunchy_log("get_in_queue: Failed to retrieve data", xbmc.LOGERROR)
        return []

    if not req.get("data"):
        return []

    return [item.get("id") for item in req.get("data")]


def highlight_list_item_title(list_item: ListItem) -> None:
    """Highlight title to show that item is already on watchlist."""
    list_item.setInfo("video", {"title": "[COLOR orange]" + list_item.getLabel() + "[/COLOR]"})
