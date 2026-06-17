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

"""Declarative mode registry for routing Kodi plugin requests.

`crunchyroll.py` calls `check_mode(ctx)`.  The mode is resolved from the
arguments or derived from an external-plugin invocation (``id`` / ``url``),
then looked up in `MODE_REGISTRY`.  Unknown modes fall back to the main menu.

Import ordering rule: this module may import from ``controller`` and
``crunchyroll``, but ``controller`` must NEVER import this module to avoid
circular imports.
"""

import xbmc
import xbmcgui

from . import controller
from .utils.logging import crunchy_log

# Disabled modes that were once exposed in the menu but have no backend support
# at the moment. Kept here so they do not accidentally get re-registered.
DEPRECATED_MODES = [
    "random",
    "featured",
    "simulcast",
    "updated",
    "remove_from_queue",
]


def check_mode(ctx):
    """Run mode-specific functions.

    A missing mode (top-level entry) silently shows the main menu.  A mode that
    is set but not registered is treated as an error: it is logged and the user
    is notified before falling back to the main menu, matching the original
    ``check_mode`` behaviour.
    """
    mode = derive_mode_from_args(ctx.args)

    if not mode:
        return show_main_menu(ctx)

    handler = MODE_REGISTRY.get(mode)
    if handler is None:
        crunchy_log(f"Failed in check_mode '{str(mode)}'", xbmc.LOGERROR, addon=ctx.args.addon)
        xbmcgui.Dialog().notification(
            ctx.args.addon_name,
            ctx.args.addon.getLocalizedString(30061),
            xbmcgui.NOTIFICATION_ERROR,
        )
        return show_main_menu(ctx)

    return handler(ctx)


def derive_mode_from_args(args):
    """Resolve the requested mode from the parsed CLI arguments.

    Returns ``None`` for the top-level entry so the main menu is shown.
    External plugin calls may pass ``id`` or ``url``; these are normalised
    to the ``videoplay`` mode and the ``url`` argument is mutated in place.
    """
    if args.get_arg("mode"):
        return args.get_arg("mode")

    if args.get_arg("id"):
        args.set_arg("url", "/media-" + args.get_arg("id"))
        return "videoplay"

    if args.get_arg("url"):
        # call from other plugin
        args.set_arg("url", args.get_arg("url")[26:])  # @todo: does this actually work? truncated?
        return "videoplay"

    return None


def _show_main_category_anime(ctx):
    """Registry wrapper for the anime category screen."""
    from . import crunchyroll

    return crunchyroll.show_main_category(ctx, "anime")


def _show_main_category_drama(ctx):
    """Registry wrapper for the drama category screen."""
    from . import crunchyroll

    return crunchyroll.show_main_category(ctx, "drama")


MODE_REGISTRY = {
    "queue": controller.show_queue,
    "search": controller.search_anime,
    "history": controller.show_history,
    "resume": controller.show_resume_episodes,
    "anime": _show_main_category_anime,
    "drama": _show_main_category_drama,
    "popular": controller.list_filter,
    "newest": controller.list_filter,
    "alpha": controller.list_filter,
    "season": controller.list_anime_seasons,
    "genre": controller.list_filter,
    "seasons": controller.view_season,
    "episodes": controller.view_episodes,
    "videoplay": controller.start_playback,
    "add_to_queue": controller.add_to_queue,
    "crunchylists_lists": controller.crunchylists_lists,
    "crunchylists_item": controller.crunchylists_item,
    "profiles_list": controller.show_profiles,
}


# Import the fallback at module level after defining MODE_REGISTRY to keep the
# registry the obvious contract while still resolving the fallback lazily on
# first lookup.
from . import crunchyroll as _crunchyroll  # noqa: E402


def show_main_menu(ctx):
    """Dispatch to the real main-menu implementation in crunchyroll.py."""
    return _crunchyroll.show_main_menu(ctx)
