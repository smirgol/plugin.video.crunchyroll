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

import json
import math

import xbmc
import xbmcgui
import xbmcvfs

from . import view
from .controller_helpers import (
    add_next_page_item,
    is_response_error,
    is_response_error_strict,
    render_error_directory,
)
from .models.account import ProfileData
from .models.exceptions import CrunchyrollError
from .utils.api_data import get_listables_from_response
from .utils.images import get_img_from_struct
from .utils.logging import crunchy_log, log_error_with_trace
from .videoplayer import VideoPlayer


def show_profiles(ctx):
    # api request
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.PROFILES_LIST_ENDPOINT,
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    profiles = req.get("profiles")
    profile_list_items = list(map(lambda profile: ProfileData(profile).to_item(ctx.args.addon), profiles))
    current_profile = 0

    if bool(ctx.api.profile_data.profile_id):
        current_profile = [
            i for i in range(len(profiles)) if profiles[i].get("profile_id") == ctx.api.profile_data.profile_id
        ][0]

    selected = xbmcgui.Dialog().select(
        ctx.args.addon.getLocalizedString(30073),
        profile_list_items,
        preselect=current_profile,
        useDetails=True,
    )

    if selected == -1:
        return True
    else:
        ctx.api.create_session(action="refresh_profile", profile_id=profiles[selected].get("profile_id"))
        return True


def show_queue(ctx):
    """shows anime queue/playlist"""
    # api request
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.WATCHLIST_LIST_ENDPOINT.format(ctx.api.account_data.account_id),
        params={
            "n": 1024,
            "locale": ctx.args.subtitle,
        },
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    view.add_listables(
        ctx,
        listables=get_listables_from_response(req.get("items"), args=ctx.args),
        is_folder=False,
        options=view.OPT_CTX_SEASONS | view.OPT_CTX_EPISODES,  # | view.OPT_SORT_EPISODES_EXPERIMENTAL
    )

    view.end_of_directory(ctx, "episodes", cache_to_disc=False)
    return True


def search_anime(ctx):
    """Search for anime"""

    # ask for search string
    if not ctx.args.get_arg("search"):
        d = xbmcgui.Dialog().input(ctx.args.addon.getLocalizedString(30041), type=xbmcgui.INPUT_ALPHANUM)
        if not d:
            return None
    else:
        d = ctx.args.get_arg("search")

    # api request
    # available types seem to be: music,series,episode,top_results,movie_listing
    # @todo: we could search for all types, then first present a listing of the types we have search results for
    #        the user then could pick one of these types and get presented with a filtered search result for that
    #        type only.
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.SEARCH_ENDPOINT,
        params={
            "n": 50,
            "q": d,
            "locale": ctx.args.subtitle,
            "start": ctx.args.get_arg("offset", 0, int),
            "type": "series",
        },
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    if not req.get("items") or len(req.get("items")) == 0:
        return render_error_directory(ctx, title_id=30090)

    type_data = req.get("items")[0]  # @todo: for now we support only the first type, which should be series

    view.add_listables(
        ctx,
        listables=get_listables_from_response(type_data.get("items"), args=ctx.args),
        is_folder=True,
        options=view.OPT_CTX_WATCHLIST | view.OPT_MARK_ON_WATCHLIST | view.OPT_CTX_SEASONS | view.OPT_CTX_EPISODES,
    )

    # pagination
    items_left = type_data.get("total") - (ctx.args.get_arg("offset", 0, int) * 50) - len(type_data.get("items"))
    if items_left > 0:
        add_next_page_item(
            ctx,
            offset=ctx.args.get_arg("offset", 0, int) + 50,
            mode=ctx.args.get_arg("mode"),
            search=d,
        )

    view.end_of_directory(ctx, "tvshows")
    return True


def show_history(ctx):
    """shows history of watched anime"""
    items_per_page = 50
    current_page = ctx.args.get_arg("offset", 1, int)

    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.HISTORY_ENDPOINT.format(ctx.api.account_data.account_id),
        params={
            "page_size": items_per_page,
            "page": current_page,
            "locale": ctx.args.subtitle,
        },
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    # episodes / episodes  (crunchy / xbmc)
    view.add_listables(
        ctx,
        listables=get_listables_from_response(req.get("data"), args=ctx.args),
        is_folder=False,
    )

    # pagination
    num_pages = int(math.ceil(req["total"] / items_per_page))
    if current_page < num_pages:
        add_next_page_item(
            ctx,
            offset=ctx.args.get_arg("offset", 1, int) + 1,
            mode=ctx.args.get_arg("mode"),
        )

    view.end_of_directory(ctx, "episodes", cache_to_disc=False)
    return True


def show_resume_episodes(ctx):
    """shows episode to resume for watching animes"""
    items_per_page = 50

    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.RESUME_ENDPOINT.format(ctx.api.account_data.account_id),
        params={
            "n": items_per_page,
            "locale": ctx.args.subtitle,
            "start": ctx.args.get_arg("offset", 0, int),
        },
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    # episodes / episodes  (crunchy / xbmc)
    view.add_listables(
        ctx,
        listables=get_listables_from_response(req.get("data"), args=ctx.args),
        is_folder=False,
        options=view.OPT_CTX_SEASONS | view.OPT_CTX_EPISODES,
    )

    # pagination
    items_left = req.get("total") - (ctx.args.get_arg("offset", 0, int) * items_per_page) - len(req.get("data"))
    if items_left > 0:
        add_next_page_item(
            ctx,
            offset=ctx.args.get_arg("offset", 0, int) + items_per_page,
            mode=ctx.args.get_arg("mode"),
        )

    view.end_of_directory(ctx, "episodes", cache_to_disc=False)

    return True


def list_anime_seasons(ctx):
    """view all available anime seasons and filter by selected season"""
    season_filter: str = ctx.args.get_arg("season_filter", "")

    # if no seasons filter applied, list all available seasons
    if not season_filter:
        return list_anime_seasons_without_filter(ctx)

    # else, if we have a season filter, show all from season
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.BROWSE_ENDPOINT,
        params={
            "locale": ctx.args.subtitle,
            "season_tag": season_filter,
            "n": 100,
        },
    )

    # check for error
    if is_response_error_strict(req):
        return render_error_directory(ctx)

    # season / season  (crunchy / xbmc)
    view.add_listables(
        ctx,
        listables=get_listables_from_response(req.get("items"), args=ctx.args),
        is_folder=True,
        options=view.OPT_CTX_WATCHLIST | view.OPT_MARK_ON_WATCHLIST | view.OPT_CTX_SEASONS | view.OPT_CTX_EPISODES,
    )

    view.end_of_directory(ctx, "seasons")
    return None


def list_anime_seasons_without_filter(ctx):
    """view all available anime seasons and filter by selected season"""
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.SEASONAL_TAGS_ENDPOINT,
        params={
            "locale": ctx.args.subtitle,
        },
    )

    # check for error
    if is_response_error_strict(req):
        return render_error_directory(ctx)

    for season_tag_item in req.get("data"):
        # add to view
        view.add_item(
            ctx,
            {
                "title": season_tag_item.get("localization", {}).get("title"),
                "season_filter": season_tag_item.get("id", {}),
                "mode": ctx.args.get_arg("mode"),
            },
            is_folder=True,
        )

    view.end_of_directory(ctx, "seasons")

    return True


def list_filter(ctx):
    """view all anime from selected mode"""
    category_filter: str = ctx.args.get_arg("category_filter", "")

    # we re-use this method which is normally used for the categories to also show some special views, that share
    # the same logic
    specials = ["popularity", "newly_added", "alphabetical"]

    # if no category_filter filter applied, list all available categories
    if not category_filter and category_filter not in specials:
        return list_filter_without_category(ctx)

    # else, if we have a category filter, show all from category

    items_per_page = ctx.args.get_arg("items_per_page", 50, int)  # change this if desired

    # default query params - might get modified by special categories below
    params = {
        "locale": ctx.args.subtitle,
        "categories": category_filter,
        "n": items_per_page,
        "start": ctx.args.get_arg("offset", 0, int),
        "ratings": "true",
    }

    # hack to re-use this for other views
    if category_filter in specials:
        params.update({"sort_by": category_filter})
        params.pop("categories")

    # api request
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.BROWSE_ENDPOINT,
        params=params,
    )

    # check for error
    if is_response_error_strict(req):
        return render_error_directory(ctx)

    # series / collection  (crunchy / xbmc)
    view.add_listables(
        ctx,
        listables=get_listables_from_response(req.get("items"), args=ctx.args),
        is_folder=True,
        options=view.OPT_CTX_WATCHLIST | view.OPT_MARK_ON_WATCHLIST | view.OPT_CTX_SEASONS | view.OPT_CTX_EPISODES,
    )

    items_left = req.get("total") - ctx.args.get_arg("offset", 0, int) - len(req.get("items"))

    # show next page button
    if items_left > 0:
        add_next_page_item(
            ctx,
            offset=ctx.args.get_arg("offset", 0, int) + items_per_page,
            mode=ctx.args.get_arg("mode"),
            category_filter=category_filter,
        )

    view.end_of_directory(ctx, "tvshows")

    return True


def list_filter_without_category(ctx):
    # api request for category names / tags
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.CATEGORIES_ENDPOINT,
        params={
            "locale": ctx.args.subtitle,
        },
    )

    # check for error
    if is_response_error_strict(req):
        return render_error_directory(ctx)

    for category_item in req.get("items"):
        try:
            # add to view
            view.add_item(
                ctx,
                {
                    "title": category_item.get("localization", {}).get("title"),
                    "plot": category_item.get("localization", {}).get("description"),
                    "plotoutline": category_item.get("localization", {}).get("description"),
                    "thumb": get_img_from_struct(category_item, "low", 1),
                    "fanart": get_img_from_struct(category_item, "background", 1),
                    "category_filter": category_item.get("tenant_category", {}),
                    "mode": ctx.args.get_arg("mode"),
                },
                is_folder=True,
            )
        except Exception:
            log_error_with_trace(
                f"Failed to add category name item to list_filter view: {json.dumps(category_item, indent=4)}"
            )

    view.end_of_directory(ctx, "tvshows")

    return True


def view_season(ctx):
    """view all seasons/arcs of an anime"""
    # api request
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.SEASONS_ENDPOINT.format(ctx.args.get_arg("series_id")),
        params={
            "locale": ctx.args.subtitle,
            "preferred_audio_language": ctx.api.account_data.default_audio_language,
            "force_locale": "",
        },
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    # season / season  (crunchy / xbmc)
    view.add_listables(
        ctx,
        listables=get_listables_from_response(
            req.get("data") or req.get("items"),
            item_type_hint="season",
            args=ctx.args,
        ),
        is_folder=True,
    )

    view.end_of_directory(ctx, "seasons")
    return True


def view_episodes(ctx):
    """view all episodes of season"""
    # api request
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.EPISODES_ENDPOINT.format(ctx.args.get_arg("season_id")),
        params={
            "locale": ctx.args.subtitle,
            "preferred_audio_language": ctx.api.account_data.default_audio_language,
            "force_locale": "",
        },
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    # episodes / episodes  (crunchy / xbmc)
    view.add_listables(
        ctx,
        listables=get_listables_from_response(
            req.get("data") or req.get("items"),
            item_type_hint="episode",
            args=ctx.args,
        ),
        is_folder=False,
        options=view.OPT_NO_SEASON_TITLE,
    )

    view.end_of_directory(ctx, "episodes", cache_to_disc=False)
    return True


def start_playback(ctx):
    """plays an episode"""
    video_player = VideoPlayer(ctx=ctx)
    video_player.start_playback()

    crunchy_log("Starting loop", xbmc.LOGINFO)
    # stay in this method while playing to not lose video_player, as backgrounds threads reference it
    monitor = ctx.monitor
    args = ctx.args
    while (not monitor.abortRequested()) and video_player.isStartingOrPlaying():
        video_player.check_skipping()
        if args.addon.getSetting("sync_playtime") == "true":
            video_player.update_playhead()
        monitor.waitForAbort(1)
    video_player.finished()
    del video_player


def add_to_queue(ctx) -> bool:
    from .models.exceptions import LoginError

    try:
        req = ctx.api.make_scraper_request(
            method="POST",
            url=ctx.api.WATCHLIST_V2_ENDPOINT.format(ctx.api.account_data.account_id),
            json_data={
                "content_id": ctx.args.get_arg("content_id"),
            },
            params={
                "locale": ctx.args.subtitle,
                "preferred_audio_language": ctx.api.account_data.default_audio_language,
            },
            headers={
                "Content-Type": "application/json",
            },
        )

        if req and "error" in req:
            error_msg = req.get("error", "Unknown error")
            if "content.add_watchlist_item_v2.item_already_exists" in error_msg:
                xbmcgui.Dialog().notification(
                    f"{ctx.args.addon_name} Error", "Item already in watchlist", xbmcgui.NOTIFICATION_ERROR, 3
                )
                return False
            else:
                raise CrunchyrollError(f"Failed to add to watchlist: {error_msg}")

    except CrunchyrollError as e:
        if "content.add_watchlist_item_v2.item_already_exists" in str(e):
            xbmcgui.Dialog().notification(
                f"{ctx.args.addon_name} Error",
                "Item already in watchlist",
                xbmcgui.NOTIFICATION_ERROR,
                3,
            )
            return False
        else:
            log_error_with_trace(f"Failed to add to queue: {e}")
            xbmcgui.Dialog().notification(
                f"{ctx.args.addon_name} Error",
                "Failed to add item to watchlist",
                xbmcgui.NOTIFICATION_ERROR,
                3,
            )
            return False
    except LoginError as e:
        log_error_with_trace(f"Authentication error adding to queue: {e}")
        xbmcgui.Dialog().notification(
            f"{ctx.args.addon_name} Error",
            "Authentication failed - it's broken, Jim! :(",
            xbmcgui.NOTIFICATION_ERROR,
            3,
        )
        return False
    except Exception as e:
        log_error_with_trace(f"Unexpected error adding to queue: {e}")
        xbmcgui.Dialog().notification(
            f"{ctx.args.addon_name} Error",
            "Failed to add item to watchlist",
            xbmcgui.NOTIFICATION_ERROR,
            3,
        )
        return False

    xbmcgui.Dialog().notification(
        ctx.args.addon_name,
        ctx.args.addon.getLocalizedString(30071),
        xbmcgui.NOTIFICATION_INFO,
        2,
        False,
    )

    return True


def crunchylists_lists(ctx):
    """Retrieve all crunchylists"""

    # api request
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.CRUNCHYLISTS_LISTS_ENDPOINT.format(ctx.api.account_data.account_id),
        params={
            "locale": ctx.args.subtitle,
        },
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    for crunchy_list in req.get("data"):
        # add to view
        view.add_item(
            ctx,
            {
                "title": crunchy_list.get("title"),
                "fanart": xbmcvfs.translatePath(ctx.args.addon.getAddonInfo("fanart")),
                "mode": "crunchylists_item",
                "crunchylists_item_id": crunchy_list.get("list_id"),
            },
            is_folder=True,
        )

    view.end_of_directory(ctx, "tvshows")

    return None


def crunchylists_item(ctx):
    """Retrieve all items for a crunchylist"""

    crunchy_log(f"Fetching crunchylist: {ctx.args.get_arg('crunchylists_item_id')}")

    # api request
    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.CRUNCHYLISTS_VIEW_ENDPOINT.format(
            ctx.api.account_data.account_id, ctx.args.get_arg("crunchylists_item_id")
        ),
        params={
            "locale": ctx.args.subtitle,
        },
    )

    # check for error
    if is_response_error(req):
        return render_error_directory(ctx)

    view.add_listables(
        ctx,
        listables=get_listables_from_response(req.get("data"), args=ctx.args),
        is_folder=True,
        options=view.OPT_CTX_SEASONS | view.OPT_CTX_EPISODES,
    )

    view.end_of_directory(ctx, "tvshows")

    return None
