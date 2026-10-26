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
