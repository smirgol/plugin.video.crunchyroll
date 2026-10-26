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

import xbmc

# Closes an open skip dialog (it closes on NOOP) instead of leaving it up until its timeout
NOOP_BUILTIN = "Action(noop)"

_ENDED = "ended"
_STOPPED = "stopped"
_ERROR = "error"


class PlaybackEndTracker:
    """Latches how playback ended; the first final event wins."""

    def __init__(self) -> None:
        self._result: str | None = None

    def on_ended(self) -> None:
        self._latch(_ENDED)

    def on_stopped(self) -> None:
        self._latch(_STOPPED)

    def on_error(self) -> None:
        self._latch(_ERROR)

    @property
    def has_result(self) -> bool:
        return self._result is not None

    @property
    def ended_regularly(self) -> bool:
        return self._result == _ENDED

    def _latch(self, result: str) -> None:
        if self._result is None:
            self._result = result


def await_end_result(tracker: PlaybackEndTracker, monitor, timeout: float = 2.0, interval: float = 0.5) -> None:
    """Give Kodi's end-of-playback callback a chance to arrive after the playback loop was left.

    Kodi only delivers the callbacks while the script is inside a Kodi call such as waitForAbort.
    """
    waited = 0.0
    while not tracker.has_result and waited < timeout:
        if monitor.waitForAbort(interval):
            return
        waited += interval


class PlaybackEndHandler:
    """Forwards Kodi end-of-playback events to the tracker."""

    def __init__(self, tracker: PlaybackEndTracker) -> None:
        self._tracker = tracker

    def ended(self) -> None:
        self._tracker.on_ended()
        xbmc.executebuiltin(NOOP_BUILTIN)

    def stopped(self) -> None:
        self._tracker.on_stopped()

    def error(self) -> None:
        self._tracker.on_error()


class PlaybackEndListener(xbmc.Player):
    """Kodi player callbacks, delegated to PlaybackEndHandler.

    Create the instance in the main thread before setResolvedUrl and keep the reference until after
    await_end_result: Kodi only delivers the callbacks while the thread is inside a Kodi call.
    Composition instead of a mixin: xbmc.Player is a MagicMock in tests, a mixin would raise a metaclass conflict.
    """

    def __init__(self, tracker: PlaybackEndTracker) -> None:
        super().__init__()
        self._handler = PlaybackEndHandler(tracker)

    def onPlayBackEnded(self) -> None:
        self._handler.ended()

    def onPlayBackStopped(self) -> None:
        self._handler.stopped()

    def onPlayBackError(self) -> None:
        self._handler.error()
