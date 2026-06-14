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

from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable
from typing import Any

import xbmcgui
import xbmcplugin
import xbmcvfs

from resources.lib.model import Args, EpisodeData, ListableItem, PlayableItem, SeasonData, SeriesData

from . import presentation, router, utils
from .context import PluginContext
from .globals import G

# Fix for bug in old python version on windows
# @see: https://github.com/smirgol/plugin.video.crunchyroll/issues/44
# @see: https://stackoverflow.com/questions/63860576/asyncio-event-loop-is-closed-when-using-asyncio-run
if sys.platform == "win32" and sys.version_info >= (3, 8, 0):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# keys allowed in setInfo - kept as backward-compat alias.
# New code should import KODI_INFO_TYPES from presentation.
types = presentation.KODI_INFO_TYPES


def _args_from(ctx: PluginContext | None) -> Args:
    """Return ctx.args if a context is provided, otherwise fall back to G.args.

    This helper keeps view.py callable from legacy code during the PluginContext
    transition. It will be removed in Phase 9c when the G singleton is deleted.
    """
    return ctx.args if ctx is not None else G.args


def end_of_directory(ctx: PluginContext | None = None, content_type=None, update_listing=False, cache_to_disc=True):
    args = _args_from(ctx)
    # let xbmc know the items type in current directory
    if content_type is not None:
        xbmcplugin.setContent(int(args.argv[1]), content_type)

    # sort methods are required in library mode
    xbmcplugin.addSortMethod(int(args.argv[1]), xbmcplugin.SORT_METHOD_NONE)

    # let xbmc know the script is done adding items to the list
    xbmcplugin.endOfDirectory(handle=int(args.argv[1]), updateListing=update_listing, cacheToDisc=cache_to_disc)


def add_item(
    ctx: PluginContext | None = None,
    info=None,
    is_folder=True,
    total_items=0,
    mediatype="video",
    callbacks: list[Callable[[xbmcgui.ListItem], None]] | None = None,
):
    """Add item to directory listing.

    This is the old, more verbose approach. Try to use view.add_listables() for adding list items, if possible
    """

    args = _args_from(ctx)
    if info is None:
        info = {}

    path_params = {}
    path_params.update(args.args)
    path_params.update(info)

    # get url
    u = presentation.build_url(path_params, args.addonurl)

    # create list item
    li = xbmcgui.ListItem(label=info.get("title", ""), path=u)

    sync = args.addon.getSetting("sync_playtime") == "true"
    # get infoLabels
    info_labels = presentation.make_info_label(info, args.args, sync_playtime=sync)

    if is_folder:
        # directory
        info_labels["mediatype"] = "tvshow"
        li.setInfo(mediatype, info_labels)
    else:
        # playable video
        info_labels["mediatype"] = "episode"
        li.setInfo(mediatype, info_labels)
        li.setProperty("IsPlayable", "true")

        # add context menu to jump to seasons xor episodes
        # @todo: this only makes sense in some very specific places, we need a way to handle these better.
        cm = []
        addonurl = args.addonurl
        if path_params.get("series_id"):
            url = presentation.build_url(path_params, addonurl, "series_view")
            cm.append((args.addon.getLocalizedString(30045), f"Container.Update({url})"))
        if path_params.get("collection_id"):
            url = presentation.build_url(path_params, addonurl, "season_view")
            cm.append((args.addon.getLocalizedString(30046), f"Container.Update({url})"))

        if len(cm) > 0:
            li.addContextMenuItems(cm)

    # set media image
    artworks = {
        "thumb": info.get("thumb", "DefaultFolder.png"),
        "fanart": info.get("fanart", xbmcvfs.translatePath(args.addon.getAddonInfo("fanart"))),
        "poster": info.get("poster", info.get("thumb", "DefaultFolder.png")),
        "landscape": info.get("landscape", info.get("thumb", "DefaultFolder.png")),
        "banner": info.get("poster", info.get("thumb", "DefaultFolder.png")),
        "icon": info.get("thumb", "DefaultFolder.png"),
    }

    if info.get("clearlogo"):
        artworks["clearlogo"] = info.get("clearlogo")
    if info.get("clearart"):
        artworks["clearart"] = info.get("clearart")

    li.setArt(artworks)

    if callbacks:
        for cb in callbacks:
            cb(li)

    # add item to list
    xbmcplugin.addDirectoryItem(
        handle=int(args.argv[1]),
        url=u,
        listitem=li,
        isFolder=is_folder,
        totalItems=total_items,
    )


OPT_MARK_ON_WATCHLIST = 1  # highlight title if item is on watchlist
OPT_CTX_WATCHLIST = 2  # add context menu to add item to watchlist
OPT_CTX_SEASONS = 4  # add context menu to jump to series
OPT_CTX_EPISODES = 8  # add context menu to jump to episodes
OPT_NO_SEASON_TITLE = 16  # only show title of episode (with numbering)
OPT_SORT_EPISODES_EXPERIMENTAL = 32  # sort un-viewed queue items to top


# actually not sure if this works, as the requests lib is not async
# also not sure if this is thread safe in any way, what if session is timed-out when starting this?
async def complement_listables(listables: list[ListableItem]) -> dict[str, dict[str, Any]]:
    # for all playable items fetch playhead data from api, as sometimes we already have them, sometimes not
    from .utils import (
        get_cms_object_data_by_ids,
        get_img_from_struct,
        get_playheads_from_api,
        get_watchlist_status_from_api,
        infer_img_from_id,
    )

    # playheads
    ids_playhead = [
        listable.id for listable in listables if isinstance(listable, PlayableItem) and listable.playhead == 0
    ]

    # object data for e.g. poster images
    # for now we use the objects to fetch the series data only, to fetch its images and its rating
    ids_objects_seasons = [
        listable.series_id for listable in listables if isinstance(listable, (SeasonData, EpisodeData, SeriesData))
    ]
    # ids_objects_other = [listable.id for listable in listables if
    #                      isinstance(listable, (EpisodeData, MovieData, SeriesData))]
    # ids_objects = ids_objects_seasons + ids_objects_other
    ids_objects = list(set(ids_objects_seasons))  # make the ids unique, as there can be duplicates

    # watchlist info for series
    ids_watchlist = [listable.id for listable in listables if isinstance(listable, SeriesData)]

    # prepare async requests
    tasks_added = []
    tasks = []
    if ids_playhead:
        tasks.append(asyncio.create_task(get_playheads_from_api(ids_playhead)))
        tasks_added.append("playheads")
    # @todo: for some reason objects endpoint stopped to deliver anything but thumbs in terms of images,
    #        but the sole reason for calling it are the additional images...
    #        for now we use the objects to fetch the series data only, to fetch its images and its rating
    if ids_objects:
        tasks.append(asyncio.create_task(get_cms_object_data_by_ids(ids_objects)))
        tasks_added.append("objects")
    if ids_watchlist:
        tasks.append(asyncio.create_task(get_watchlist_status_from_api(ids_watchlist)))
        tasks_added.append("watchlist")

    # start async requests and fetch results
    results = await asyncio.gather(*tasks)

    result_obj = {
        "playheads": {},
        "objects": {},
        "watchlist": {},
    }
    for idx, task in enumerate(tasks_added):
        result_obj[task] = results[idx]

    # crunchy_log(args, "Retrieved data for playheads:")
    # dump(result_obj.get('playheads'))

    # crunchy_log(args, "Retrieved data for objects:")
    # dump(result_obj.get('objects'))
    # crunchy_log(args, "Retrieved data for watchlist:")
    # dump(result_obj.get('watchlist'))

    # add some of the info to the listables
    for listable in listables:
        # update playcount data, which might be missing
        if listable.id in result_obj.get("playheads"):
            listable.update_playcount_from_playhead(result_obj.get("playheads").get(listable.id))

        # update images for SeasonData, as they come with none by default
        if isinstance(listable, (SeriesData, SeasonData)) and listable.series_id in result_obj.get("objects"):
            series_data = result_obj.get("objects").get(listable.series_id)
            series_id = series_data.get("id") if series_data else None

            listable.thumb = get_img_from_struct(series_data, "poster_wide", 2) or listable.thumb
            listable.landscape = get_img_from_struct(series_data, "poster_wide", 2) or listable.landscape
            listable.fanart = (
                infer_img_from_id(series_id, "backdrop_wide")
                or get_img_from_struct(series_data, "poster_wide", 2)
                or listable.fanart
            )
            listable.clearlogo = infer_img_from_id(series_id, "title_logo") or listable.clearlogo
            listable.clearart = infer_img_from_id(series_id, "title_logo") or listable.clearart
            listable.poster = get_img_from_struct(series_data, "poster_tall", 2) or listable.poster

        elif isinstance(listable, EpisodeData) and listable.series_id in result_obj.get("objects"):
            # for episodes, only thumb is provided, so we can use it
            # however, fanart and other arts are empty so we need to get them from the series
            # to get a complete interface
            series_data = result_obj.get("objects").get(listable.series_id)
            series_id = series_data.get("id") if series_data else None

            listable.landscape = get_img_from_struct(series_data, "poster_wide", 2) or listable.landscape
            listable.fanart = (
                infer_img_from_id(series_id, "backdrop_wide")
                or get_img_from_struct(series_data, "poster_wide", 2)
                or listable.fanart
            )
            listable.clearlogo = infer_img_from_id(series_id, "title_logo") or listable.clearlogo
            listable.clearart = infer_img_from_id(series_id, "title_logo") or listable.clearart
            listable.poster = get_img_from_struct(series_data, "poster_tall", 2) or listable.poster

        if (
            listable.id in result_obj.get("objects")
            and result_obj.get("objects").get(listable.id).get("rating")
            and hasattr(listable, "rating")
        ):
            if result_obj.get("objects").get(listable.id).get("rating").get("average"):
                listable.rating = float(result_obj.get("objects").get(listable.id).get("rating").get("average")) * 2.0
            elif result_obj.get("objects").get(listable.id).get("rating").get("up") and result_obj.get("objects").get(
                listable.id
            ).get("rating").get("down"):
                # these are user ratings, and they are pretty weird (overly positive)
                ups_obj = result_obj.get("objects").get(listable.id).get("rating").get("up")
                downs_obj = result_obj.get("objects").get(listable.id).get("rating").get("down")
                ups = float(ups_obj.get("displayed"))
                downs = float(downs_obj.get("displayed"))

                if ups_obj.get("unit") == "K":
                    ups *= 1000.0
                elif ups_obj.get("unit") == "M":
                    ups *= 1000000.0  # not sure if that works or if there are ever that many votes

                if downs_obj.get("unit") == "K":
                    downs *= 1000.0
                elif downs_obj.get("unit") == "M":
                    downs *= 1000000.0  # not sure if that works or if there are ever that many votes

                listable.rating = float((ups / (ups + downs)) * 10.0)

    # return collected data for further usage
    return result_obj


def add_listables(
    ctx: PluginContext | None = None,
    listables: list[ListableItem] = None,
    is_folder=True,
    options: int = 0,
    callbacks: list[Callable[[xbmcgui.ListItem, ListableItem], None]] | None = None,
):
    if listables is None:
        listables = []

    from .utils import crunchy_log, highlight_list_item_title

    args = _args_from(ctx)

    crunchy_log("add_listables: Starting to retrieve data async")
    complement_data = asyncio.run(complement_listables(listables))
    crunchy_log("add_listables: Finished to retrieve data async")

    if options and options & OPT_SORT_EPISODES_EXPERIMENTAL:  # needs check for episodes
        from .utils import sort_episodes

        listables = sort_episodes(listables)

    # add listable items to kodi
    for listable in listables:
        # get url
        u = presentation.build_url(listable.get_info(), args.addonurl)

        # get xbmc list item
        list_item = listable.to_item()

        # call any callbacks
        if callbacks:
            for cb in callbacks:
                cb(list_item, listable)

        # process options

        if options & OPT_MARK_ON_WATCHLIST:
            highlight_list_item_title(list_item) if listable.id in complement_data.get("watchlist") else None

        cm = []
        if options & OPT_CTX_WATCHLIST and listable.id not in complement_data.get("watchlist"):
            cm.append(
                (
                    args.addon.getLocalizedString(30067),
                    f"RunPlugin({args.argv[0]}?mode=add_to_queue&content_id={listable.id})",
                )
            )

        if options & OPT_CTX_SEASONS and hasattr(listable, "series_id") and listable.series_id is not None:
            route = args.addonurl + router.create_path_from_route("series_view", {"series_id": listable.series_id})
            cm.append((args.addon.getLocalizedString(30045), f"Container.Update({route})"))

        if options & OPT_CTX_EPISODES and hasattr(listable, "season_id") and listable.season_id is not None:
            route = args.addonurl + router.create_path_from_route(
                "season_view", {"series_id": listable.series_id, "season_id": listable.season_id}
            )
            cm.append((args.addon.getLocalizedString(30046), f"Container.Update({route})"))

        if options & OPT_NO_SEASON_TITLE and isinstance(listable, EpisodeData):
            list_item.setInfo(
                "video", {"title": utils.format_short_episode_title(listable.episode, listable.title_unformatted)}
            )

        if len(cm) > 0:
            list_item.addContextMenuItems(cm)

        # add item to list
        xbmcplugin.addDirectoryItem(
            handle=int(args.argv[1]),
            url=u,
            listitem=list_item,
            isFolder=is_folder,
        )


def build_url(ctx: PluginContext | None = None, path_params: dict = None, route_name: str = None) -> str:
    """Create url. Backward-compat wrapper around presentation.build_url()."""
    args = _args_from(ctx)
    if path_params is None:
        path_params = {}
    return presentation.build_url(path_params, args.addonurl, route_name)


def make_info_label(ctx: PluginContext | None = None, info=None) -> dict:
    """Generate info_labels from existing dict. Backward-compat wrapper."""
    args = _args_from(ctx)
    if info is None:
        info = {}
    sync = args.addon.getSetting("sync_playtime") == "true"
    return presentation.make_info_label(info, args.args, sync_playtime=sync)
