# Crunchyroll
# Copyright (C) 2026 smirgol
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

import threading
from typing import NamedTuple

import xbmc

from ..context import PluginContext
from ..gui import NextEpisodeDialog
from ..models.content import EpisodeData
from ..utils.logging import crunchy_log
from .countdown import Countdown, NextEpisodeChoice, read_countdown_seconds

NEXT_EPISODE_XML = "plugin-video-crunchyroll-next-episode.xml"
# a dangling skip alarm would otherwise send a NOOP action later and hit the next episode dialog
CANCEL_SKIP_ALARM_BUILTIN = "CancelAlarm(closedialog,true)"
TICK_THREAD_JOIN_TIMEOUT = 2.0


class NextEpisodeLabels(NamedTuple):
    header: str
    play: str
    cancel: str
    countdown_format: str  # contains exactly one %d


def should_offer_next_episode(ended_regularly: bool, abort_requested: bool, next_episode: EpisodeData | None) -> bool:
    return ended_regularly and not abort_requested and next_episode is not None


def offer_next_episode(ctx: PluginContext, episode: EpisodeData) -> NextEpisodeChoice:
    xbmc.executebuiltin(CANCEL_SKIP_ALARM_BUILTIN)

    addon = ctx.args.addon
    countdown = Countdown(read_countdown_seconds(addon))
    stop_event = threading.Event()
    labels = NextEpisodeLabels(*(addon.getLocalizedString(string_id) for string_id in (30502, 30503, 30504, 30505)))
    dialog = NextEpisodeDialog(
        NEXT_EPISODE_XML,
        addon.getAddonInfo("path"),
        "default",
        "1080i",
        series_title=episode.tvshowtitle or "",
        episode_title=episode.title or "",
        thumb=episode.thumb or "",
        labels=labels,
        countdown=countdown,
        stop_event=stop_event,
        abort_requested=ctx.monitor.abortRequested,
    )

    try:
        dialog.doModal()
    finally:
        stop_event.set()
        if dialog.tick_thread is not None:
            dialog.tick_thread.join(timeout=TICK_THREAD_JOIN_TIMEOUT)

    choice = NextEpisodeChoice.CANCEL if ctx.monitor.abortRequested() else countdown.result
    if choice is None:
        choice = NextEpisodeChoice.CANCEL

    crunchy_log(f"next episode dialog result: {choice.value}", xbmc.LOGINFO)
    return choice
