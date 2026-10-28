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

import re
from typing import NamedTuple, Protocol

import xbmc
import xbmcgui

from ..utils.logging import crunchy_log
from .countdown import NextEpisodeChoice
from .settings import read_clamped_int

CHAIN_PROPERTY = "plugin.video.crunchyroll.next_episode.chain"
HOME_WINDOW_ID = 10000
PRESENCE_SETTING = "next_episode_still_watching_after"
DEFAULT_PRESENCE_LIMIT = 3
MIN_PRESENCE_LIMIT = 0
MAX_PRESENCE_LIMIT = 10

# ASCII digits only; "²".isdigit() would be True
_HANDOFF_PATTERN = re.compile(r"([0-9]+):(.+)")


class ChainHandoff(NamedTuple):
    streak: int
    episode_id: str


class ChainStore(Protocol):
    """Carries one handoff value from the playing process to the one it starts."""

    def take(self) -> object:
        """Returns the stored value and clears it."""
        ...

    def put(self, value: str) -> None: ...


def parse_handoff(value: object) -> ChainHandoff | None:
    """Parses "<streak>:<episode_id>"; anything else is no handoff."""
    if not isinstance(value, str):
        return None
    match = _HANDOFF_PATTERN.fullmatch(value)
    if match is None:
        return None
    return ChainHandoff(int(match.group(1)), match.group(2))


def format_handoff(handoff: ChainHandoff) -> str:
    return f"{handoff.streak}:{handoff.episode_id}"


def _matches(handoff: ChainHandoff | None, current_episode_id: object) -> bool:
    return handoff is not None and isinstance(current_episode_id, str) and handoff.episode_id == current_episode_id


def streak_for(handoff: ChainHandoff | None, current_episode_id: object) -> int:
    """Continues the streak only for the episode the handoff was made for."""
    if handoff is not None and _matches(handoff, current_episode_id):
        return handoff.streak
    return 0


def asks_presence(streak: int, limit: int) -> bool:
    return limit > 0 and streak >= limit


def handoff_after(choice: NextEpisodeChoice, streak: int, episode_id: object) -> ChainHandoff | None:
    """Only an unanswered countdown continues the streak; anything else hands nothing over."""
    if choice is NextEpisodeChoice.TIMEOUT and isinstance(episode_id, str) and episode_id:
        return ChainHandoff(streak + 1, episode_id)
    return None


def read_presence_limit(addon) -> int:
    return read_clamped_int(addon, PRESENCE_SETTING, DEFAULT_PRESENCE_LIMIT, MIN_PRESENCE_LIMIT, MAX_PRESENCE_LIMIT)


def consume_streak(store: ChainStore, current_episode_id: object) -> int:
    """Reads and clears the handoff and returns the streak it carries for this episode. Never raises."""
    try:
        raw = store.take()
    except Exception:
        raw = None
    handoff = parse_handoff(raw)
    streak = streak_for(handoff, current_episode_id)
    if handoff is None:
        message = "next episode chain: no handoff"
    elif not _matches(handoff, current_episode_id):
        message = "next episode chain: no handoff (other episode)"
    else:
        message = f"next episode chain: handoff matched, streak {streak}"
    crunchy_log(message, xbmc.LOGINFO)
    return streak


def publish_handoff(store: ChainStore, handoff: ChainHandoff) -> None:
    """Stores the handoff for the next process. Never raises: continuing to watch beats the safeguard."""
    try:
        store.put(format_handoff(handoff))
    except Exception:
        crunchy_log("next episode chain: could not store handoff", xbmc.LOGWARNING)


class HomeWindowChainStore:
    """Kodi adapter: a Home window property survives plugin processes and is gone after a Kodi restart."""

    def __init__(self) -> None:
        self._window = xbmcgui.Window(HOME_WINDOW_ID)

    def take(self) -> str:
        value = self._window.getProperty(CHAIN_PROPERTY)
        self._window.clearProperty(CHAIN_PROPERTY)
        return value

    def put(self, value: str) -> None:
        self._window.setProperty(CHAIN_PROPERTY, value)
