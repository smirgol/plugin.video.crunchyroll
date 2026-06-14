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

import sys
import traceback
from json import dumps
from typing import TYPE_CHECKING

import xbmc
import xbmcgui

if TYPE_CHECKING:
    import xbmcaddon


def dump(data) -> None:
    xbmc.log(dumps(data, indent=4), xbmc.LOGINFO)


def log(message) -> None:
    xbmc.log(message, xbmc.LOGINFO)


def _addon_name(addon: xbmcaddon.Addon | None) -> str:
    try:
        return addon.getAddonInfo("name") if addon is not None else "Crunchyroll"
    except Exception:
        return "Crunchyroll"


def crunchy_log(message, loglevel=xbmc.LOGINFO, *, addon: xbmcaddon.Addon | None = None) -> None:
    addon_name = _addon_name(addon)
    try:
        xbmc.log(f"[PLUGIN] {addon_name}: {str(message)}", loglevel)
    except (NameError, AttributeError):
        xbmc.log(f"[PLUGIN] {addon_name}: {str(message)}", xbmc.LOGINFO)


def log_error_with_trace(message, show_notification: bool = True, *, addon: xbmcaddon.Addon | None = None) -> None:
    ex_type, ex_value, ex_traceback = sys.exc_info()
    trace_back = traceback.extract_tb(ex_traceback)

    stack_trace = []
    for trace in trace_back:
        stack_trace.append(f"File : {trace[0]} , Line : {trace[1]}, Func.Name : {trace[2]}, Message : {trace[3]}")

    addon_name = _addon_name(addon)

    xbmc.log(f"[PLUGIN] {addon_name}: {str(message)}", xbmc.LOGERROR)
    formatted_trace = "\n".join(stack_trace)
    xbmc.log(f"[PLUGIN] {addon_name}: {ex_type.__name__} {ex_value}\n{formatted_trace}", xbmc.LOGERROR)

    if show_notification:
        xbmcgui.Dialog().notification(
            f"{addon_name} Error",
            "Please check logs for details",
            xbmcgui.NOTIFICATION_ERROR,
            5,
        )


def show_user_friendly_error(
    error_type: str,
    technical_message: str = None,
    *,
    addon: xbmcaddon.Addon | None = None,
) -> None:
    """
    Show user-friendly error notification to user (translated)
    while keeping technical logs in English for developers.
    """
    error_messages = {
        "network": 30400,
        "auth_expired": 30401,
        "server": 30402,
        "cancelled": 30403,
        "expired": 30404,
        "general": 30405,
    }

    addon_name = _addon_name(addon)

    if technical_message:
        crunchy_log(f"Error ({error_type}): {technical_message}", xbmc.LOGERROR, addon=addon)

    message_id = error_messages.get(error_type, 30405)
    user_message = (
        addon.getLocalizedString(message_id)
        if addon is not None
        else f"Error {error_type}"
    )

    xbmcgui.Dialog().notification(
        f"{addon_name} Error",
        user_message,
        xbmcgui.NOTIFICATION_ERROR,
        8000,
    )
