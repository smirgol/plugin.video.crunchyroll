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

import random
import re

import xbmcaddon
import xbmcgui
import xbmcplugin

from . import controller, modes, view
from .context import PluginContext
from .globals import G
from .models.exceptions import CrunchyrollError, LoginError
from .utils.images import get_img_from_static
from .utils.logging import show_user_friendly_error


def main(argv):
    """Main function for the addon"""

    G.init(argv)

    # Build explicit context. Legacy code may still fall back to G during transition.
    ctx = PluginContext(api=G.api, args=G.args, monitor=G.monitor)

    # inputstream adaptive settings
    if ctx.args.get_arg("mode") == "hls":
        from inputstreamhelper import Helper  # noqa

        is_helper = Helper("hls")
        if is_helper.check_inputstream():
            xbmcaddon.Addon(id="inputstream.adaptive").openSettings()
        return True

    # Initialize device ID if not present
    ctx.args._device_id = ctx.args.addon.getSetting("device_id")
    if not ctx.args.device_id:
        char_set = "0123456789abcdefghijklmnopqrstuvwxyz0123456789"
        ctx.args._device_id = (
            "".join(random.sample(char_set, 8))
            + "-KODI-"
            + "".join(random.sample(char_set, 4))
            + "-"
            + "".join(random.sample(char_set, 4))
            + "-"
            + "".join(random.sample(char_set, 12))
        )
        ctx.args.addon.setSetting("device_id", ctx.args.device_id)

    # get subtitle language
    ctx.args._subtitle = ctx.args.addon.getSetting("subtitle_language")
    ctx.args._subtitle_fallback = ctx.args.addon.getSetting("subtitle_language_fallback")  # @todo: test with empty

    # temporary dialog to notify about subtitle settings change
    # @todo: remove eventually
    if ctx.args.subtitle is int or ctx.args.subtitle_fallback is int or re.match("^([0-9]+)$", ctx.args.subtitle):
        xbmcgui.Dialog().notification(
            f"{ctx.args.addon_name} INFO",
            "Language settings have changed. Please adjust settings.",
            xbmcgui.NOTIFICATION_INFO,
            10,
        )

    # handle settings->clear session data
    if ctx.args.get_arg("mode") and ctx.args.get_arg("mode") == "delete_account_data":
        ctx.api.delete_account_data()
        xbmcgui.Dialog().ok(
            ctx.args.addon_name,
            ctx.args.addon.getLocalizedString(30244),
        )
        return True

    # Start API authentication (uses device authentication)
    try:
        ctx.api.start()

        # request to select profile if not set already
        if ctx.api.profile_data.profile_id is None:
            controller.show_profiles(ctx)

        # list menu
        xbmcplugin.setContent(int(ctx.args.argv[1]), "tvshows")

        return check_mode(ctx)
    except (LoginError, CrunchyrollError) as e:
        # login failed - determine error type and show user-friendly message
        error_message = str(e).lower()

        if "cancelled" in error_message:
            error_type = "cancelled"
        elif "expired" in error_message or "token" in error_message:
            error_type = "auth_expired"
        elif "network" in error_message or "connection" in error_message:
            error_type = "network"
        elif "server" in error_message or "unavailable" in error_message:
            error_type = "server"
        else:
            error_type = "general"

        show_user_friendly_error(error_type, f"Authentication failed: {str(e)}")

        view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30060)})
        view.end_of_directory(ctx)

        return False


def check_mode(ctx):
    """Run mode-specific functions via the declarative registry."""
    return modes.check_mode(ctx)


def show_main_menu(ctx):
    """Show main menu"""
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30040), "mode": "queue"})
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30047), "mode": "resume"})
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30041), "mode": "search"})
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30042), "mode": "history"})
    # #view.add_item(ctx, args,
    # #              {"title": G.args.addon.getLocalizedString(30043),
    # #               "mode":  "random"})
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30050), "mode": "anime"})
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30049), "mode": "crunchylists_lists"})
    view.add_item(
        ctx,
        {
            "title": ctx.args.addon.getLocalizedString(30072) % str(ctx.api.profile_data.profile_name),
            "mode": "profiles_list",
            "thumb": get_img_from_static(ctx.api.profile_data.avatar),
        },
    )
    # @TODO: i think there are no longer dramas. should we add music videos and movies?
    # view.add_item(ctx, args,
    #              {"title": G.args.addon.getLocalizedString(30051),
    #               "mode":  "drama"})
    view.end_of_directory(ctx, update_listing=True, cache_to_disc=False)


def show_main_category(ctx, genre):
    """Show main category"""
    # view.add_item(ctx, args,
    #               {"title": G.args.addon.getLocalizedString(30058),
    #                "mode": "featured",
    #                "category_filter": "popular",
    #                "genre": genre})
    view.add_item(
        ctx,
        {
            "title": ctx.args.addon.getLocalizedString(30052),
            "category_filter": "popularity",
            "mode": "popular",
            "genre": genre,
        },
    )
    # view.add_item(ctx, args,
    #               {"title": "TODO | " + G.args.addon.getLocalizedString(30053),
    #                "mode": "simulcast",
    #                "genre": genre})
    # view.add_item(ctx, args,
    #               {"title": "TODO | " + G.args.addon.getLocalizedString(30054),
    #                "mode": "updated",
    #                "genre": genre})
    view.add_item(
        ctx,
        {
            "title": ctx.args.addon.getLocalizedString(30059),
            "category_filter": "newly_added",
            "mode": "newest",
            "genre": genre,
        },
    )
    view.add_item(
        ctx,
        {
            "title": ctx.args.addon.getLocalizedString(30055),
            "category_filter": "alphabetical",
            "items_per_page": 100,
            "mode": "alpha",
            "genre": genre,
        },
    )
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30057), "mode": "season", "genre": genre})
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(30056), "mode": "genre", "genre": genre})
    view.end_of_directory(ctx)
