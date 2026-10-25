# Crunchyroll
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

"""Integration with the Up Next add-on (service.upnext).

Up Next is notified through a JSON-RPC ``NotifyAll`` signal carrying the current and the next episode.
See https://github.com/im85288/service.upnext/wiki/Integration for the contract.
"""

from __future__ import annotations

import base64
import json

import xbmc
import xbmcaddon

from . import presentation
from .context import PluginContext
from .models.content import EpisodeData
from .models.exceptions import CrunchyrollError
from .utils.api_data import get_listables_from_response
from .utils.language import LanguagePreferences, season_versions, select_season_versions
from .utils.logging import crunchy_log

UPNEXT_ADDON_ID = "service.upnext"
SIGNAL_MESSAGE = "upnext_data"
MIN_SKIP_SEGMENTS_VERSION = (1, 3, 0)


def is_upnext_installed() -> bool:
    return bool(xbmc.getCondVisibility(f"System.AddonIsEnabled({UPNEXT_ADDON_ID})"))


def supports_skip_segments() -> bool:
    """Intro skipping (``skip_segments``) exists from Up Next 1.3.0; older versions silently ignore it."""
    try:
        version = xbmcaddon.Addon(UPNEXT_ADDON_ID).getAddonInfo("version")
        parts = tuple(int(part) for part in version.split("-")[0].split(".")[:3])
    except (RuntimeError, ValueError):
        return False
    return parts >= MIN_SKIP_SEGMENTS_VERSION


def is_enabled(args) -> bool:
    """The user switched the Up Next integration on."""
    return args.addon.getSetting("enable_upnext") == "true"


def replaces_native_skip(args) -> bool:
    """Up Next takes over intro skipping and the credits prompt; the built-in skip is then not used.

    Only when the installed Up Next can skip intros, so older versions don't leave the user without a skip.
    """
    return (
        is_enabled(args)
        and args.addon.getSetting("upnext_replace_skip") == "true"
        and is_upnext_installed()
        and supports_skip_segments()
    )


def _is_error(req: dict | None) -> bool:
    return not req or "error" in req


def _episodes_of_season(ctx: PluginContext, season_id: str, audio: str | None) -> list[EpisodeData]:
    params = {"locale": ctx.args.subtitle}
    if audio:
        params["preferred_audio_language"] = audio

    req = ctx.api.make_request(method="GET", url=ctx.api.EPISODES_ENDPOINT.format(season_id), params=params)
    if _is_error(req):
        return []

    episodes = []
    for item in req.get("data") or req.get("items") or []:
        # an item without stream link makes the parser raise; it is unplayable anyway, so drop just that one
        try:
            listables = get_listables_from_response([item], item_type_hint="episode", args=ctx.args)
        except CrunchyrollError:
            continue
        episodes.extend(listable for listable in listables if isinstance(listable, EpisodeData))
    if audio:
        episodes = [episode for episode in episodes if episode.audio_locale == audio]
    return episodes


def _is_playable(episode: EpisodeData) -> bool:
    return bool(episode.episode_id and episode.stream_id)


def _is_same_episode(episode: EpisodeData, episode_id: str) -> bool:
    return episode.episode_id == episode_id or any(v.get("guid") == episode_id for v in episode.versions)


def _next_in_list(episodes: list[EpisodeData], current_id: str) -> EpisodeData | None:
    for index, episode in enumerate(episodes):
        if _is_same_episode(episode, current_id):
            return next((e for e in episodes[index + 1 :] if _is_playable(e)), None)
    return None


def _first_of_following_seasons(ctx: PluginContext, current: EpisodeData) -> EpisodeData | None:
    """First playable episode of the next season that has episodes, in the audio of the current episode."""
    if not current.series_id or not current.season_id:
        return None

    req = ctx.api.make_request(
        method="GET",
        url=ctx.api.SEASONS_ENDPOINT.format(current.series_id),
        params={"locale": ctx.args.subtitle},
    )
    if _is_error(req):
        return None

    seasons = req.get("data") or req.get("items") or []
    position = next(
        (i for i, season in enumerate(seasons) if any(v["id"] == current.season_id for v in season_versions(season))),
        None,
    )
    if position is None:
        return None

    prefs = LanguagePreferences.from_args(ctx.args)
    for season in seasons[position + 1 :]:
        if current.audio_locale:
            variants = [v for v in season_versions(season) if v.get("audio_locale") == current.audio_locale]
        else:
            variants = select_season_versions([season], prefs)[:1]
        if not variants:
            continue

        episodes = _episodes_of_season(ctx, variants[0]["id"], current.audio_locale)
        first = next((e for e in episodes if _is_playable(e)), None)
        if first:
            return first
    return None


def find_next_episode(ctx: PluginContext, current: EpisodeData) -> EpisodeData | None:
    """Next playable episode after *current*, continuing into the following seasons of the series."""
    if current.season_id and current.episode_id:
        episodes = _episodes_of_season(ctx, current.season_id, current.audio_locale)
        next_episode = _next_in_list(episodes, current.episode_id)
        if next_episode:
            return next_episode

    return _first_of_following_seasons(ctx, current)


def _episode_payload(episode: EpisodeData) -> dict:
    return {
        "episodeid": episode.episode_id or "",
        "tvshowid": episode.series_id or "",
        "title": episode.title_unformatted or episode.title or "",
        "art": {
            "thumb": episode.thumb or "",
            "tvshow.clearart": episode.clearart or "",
            "tvshow.clearlogo": episode.clearlogo or "",
            "tvshow.fanart": episode.fanart or "",
            "tvshow.landscape": episode.landscape or "",
            "tvshow.poster": episode.poster or "",
        },
        "season": episode.season,
        "episode": episode.episode,
        "showtitle": episode.tvshowtitle or "",
        "plot": episode.plot or "",
        "playcount": episode.playcount,
        "rating": episode.rating,
        "firstaired": episode.aired or "",
        "runtime": episode.duration,
    }


def _timing_payload(current: EpisodeData, skip_events: dict | None) -> dict:
    """Credits start as prompt position and the intro as skip segment, from Crunchyroll's skip events."""
    timing: dict = {}
    skip_events = skip_events or {}

    credits_start = (skip_events.get("credits") or {}).get("start")
    if credits_start is not None and 0 < credits_start and (not current.duration or credits_start < current.duration):
        timing["notification_offset"] = int(credits_start)

    intro = skip_events.get("intro") or {}
    if intro.get("start") is not None and intro.get("end") is not None and intro["start"] < intro["end"]:
        timing["skip_segments"] = [{"kind": "intro", "start": int(intro["start"]), "end": int(intro["end"])}]

    return timing


def build_payload(
    current: EpisodeData,
    next_episode: EpisodeData,
    play_url: str,
    skip_events: dict | None = None,
    use_skip_events: bool = False,
) -> dict:
    payload = {
        "current_episode": _episode_payload(current),
        "next_episode": _episode_payload(next_episode),
        "play_url": play_url,
    }
    if use_skip_events:
        payload.update(_timing_payload(current, skip_events))
    return payload


def send_payload(addon_id: str, payload: dict) -> bool:
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "JSONRPC.NotifyAll",
        "params": {"sender": f"{addon_id}.SIGNAL", "message": SIGNAL_MESSAGE, "data": [encoded]},
    }

    response = json.loads(xbmc.executeJSONRPC(json.dumps(request)))
    if response.get("result") != "OK":
        crunchy_log(f"Up Next notification failed: {response}", xbmc.LOGERROR)
        return False
    return True


def notify_next_episode(ctx: PluginContext, current, skip_events: dict | None = None) -> bool:
    """Tell Up Next about the next episode; returns True when a notification was sent."""
    if not isinstance(current, EpisodeData):
        return False

    next_episode = find_next_episode(ctx, current)
    if not next_episode:
        crunchy_log("Up Next: no next episode found", xbmc.LOGINFO)
        return False

    play_url = presentation.build_url(next_episode.get_info(), ctx.args.addonurl)
    payload = build_payload(
        current, next_episode, play_url, skip_events=skip_events, use_skip_events=replaces_native_skip(ctx.args)
    )
    return send_payload(ctx.args.addon_id, payload)
