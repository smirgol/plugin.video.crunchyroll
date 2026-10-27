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

from typing import Mapping

import xbmc

from ..context import PluginContext
from ..controller_helpers import is_response_error
from ..models.base import PlayableItem
from ..models.content import EpisodeData
from ..utils.api_data import get_listables_from_response
from ..utils.language import LanguagePreferences, wanted_episode_version
from ..utils.logging import crunchy_log

PREFETCH_MIN_POSITION_SECONDS = 120.0
PREFETCH_MIN_FRACTION = 0.5
SKIP_LEAD_SECONDS = 5.0


def pick_next_episode(
    episodes: list[EpisodeData], current: EpisodeData, prefs: LanguagePreferences
) -> EpisodeData | None:
    """The episode following ``current`` within ``episodes``, in the audio the viewer is already listening to."""

    current_in_list = next((episode for episode in episodes if episode.id == current.id), None)
    if current_in_list is None or current_in_list.next_episode_id is None:
        return None

    candidate = next((episode for episode in episodes if episode.id == current_in_list.next_episode_id), None)
    if candidate is None:
        return None

    if candidate.availability_status not in (None, "available") or not candidate.stream_id:
        return None

    _use_audio_of(candidate, current, prefs)
    return candidate


def _use_audio_of(candidate: EpisodeData, current: EpisodeData, prefs: LanguagePreferences) -> None:
    if current.audio_locale:
        if candidate.audio_locale == current.audio_locale:
            return

        own_version = next(
            (
                version
                for version in candidate.versions
                if version.get("audio_locale") == current.audio_locale
                and all(version.get(key) for key in ("guid", "media_guid", "season_guid"))
            ),
            None,
        )
        if own_version is not None:
            candidate.use_version(own_version)
            return

    wanted_version = wanted_episode_version(candidate, prefs)
    if wanted_version is not None:
        candidate.use_version(wanted_version)


def fetch_next_episode(ctx: PluginContext, current: PlayableItem | None) -> EpisodeData | None:
    """Look up the episode after ``current``; any failure yields None, as it must never break the end of playback."""

    if not isinstance(current, EpisodeData) or not current.season_id:
        return None

    try:
        params = {"locale": ctx.args.subtitle}
        if current.audio_locale:
            params["preferred_audio_language"] = current.audio_locale

        req = ctx.api.make_request(
            method="GET",
            url=ctx.api.EPISODES_ENDPOINT.format(current.season_id),
            params=params,
        )
        if is_response_error(req):
            crunchy_log("next episode: episodes request failed", xbmc.LOGWARNING)
            return None

        listables = get_listables_from_response(
            req.get("data") or req.get("items") or [],
            item_type_hint="episode",
            args=ctx.args,
        )
        episodes = [listable for listable in listables if isinstance(listable, EpisodeData)]

        next_episode = pick_next_episode(episodes, current, LanguagePreferences.from_args(ctx.args))
    except Exception as e:
        crunchy_log(f"next episode: lookup failed: {type(e).__name__}: {e}", xbmc.LOGWARNING)
        return None

    if next_episode is None:
        crunchy_log("next episode: none found", xbmc.LOGINFO)
        return None

    crunchy_log(f"next episode: {next_episode.id} {next_episode.audio_locale}", xbmc.LOGINFO)
    return next_episode


class PrefetchTrigger:
    """Decides exactly once during playback that the next episode should be prefetched.

    The prefetch blocks the playback loop for the duration of one request, so it must not fall into a skip
    window that is still pending: the lead buffer keeps ``check_skipping`` from missing an upcoming window.
    """

    def __init__(self) -> None:
        self._fired = False

    def should_fetch(self, position: float, total: float, skip_events: Mapping[str, Mapping[str, int]]) -> bool:
        if self._fired:
            return False

        threshold = (
            min(PREFETCH_MIN_POSITION_SECONDS, total * PREFETCH_MIN_FRACTION)
            if total > 0
            else PREFETCH_MIN_POSITION_SECONDS
        )
        if position < threshold:
            return False

        for event in skip_events.values():
            start, end = event.get("start"), event.get("end")
            if start is None or end is None:
                continue
            if start - SKIP_LEAD_SECONDS <= position < end:
                return False

        self._fired = True
        return True
