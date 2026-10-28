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
from enum import Enum
from typing import Callable

from ..gui import (
    ACTION_NAV_BACK,
    ACTION_PLAYER_STOP,
    ACTION_PREVIOUS_MENU,
    NEXT_EPISODE_BUTTON_CANCEL,
    NEXT_EPISODE_BUTTON_CONTINUE,
)


class NextEpisodeChoice(Enum):
    CONTINUE = "continue"
    TIMEOUT = "timeout"
    CANCEL = "cancel"


DEFAULT_COUNTDOWN_SECONDS = 15
MIN_COUNTDOWN_SECONDS = 5
MAX_COUNTDOWN_SECONDS = 60
COUNTDOWN_SETTING = "next_episode_countdown"

# ACTION_NOOP is deliberately not a cancel action: a dangling skip alarm must not close the dialog
_CANCEL_ACTIONS = (ACTION_PREVIOUS_MENU, ACTION_NAV_BACK, ACTION_PLAYER_STOP)


class ChoiceLatch:
    """Holds the first final decision (confirm, cancel, timeout); later ones are ignored."""

    def __init__(self) -> None:
        self._result: NextEpisodeChoice | None = None
        self._lock = threading.Lock()

    @property
    def result(self) -> NextEpisodeChoice | None:
        return self._result

    @property
    def is_finished(self) -> bool:
        return self._result is not None

    def confirm(self) -> bool:
        return self._finish(NextEpisodeChoice.CONTINUE)

    def cancel(self) -> bool:
        return self._finish(NextEpisodeChoice.CANCEL)

    def time_out(self) -> bool:
        return self._finish(NextEpisodeChoice.TIMEOUT)

    def _finish(self, choice: NextEpisodeChoice) -> bool:
        with self._lock:
            if self._result is not None:
                return False
            self._result = choice
            return True


class Countdown:
    """Counts down to a timeout; the first final state (confirm, cancel, timeout) wins."""

    def __init__(self, seconds: int) -> None:
        if seconds < 1:
            raise ValueError("seconds must be at least 1")
        self._total = seconds
        self._remaining = seconds
        self._decision = ChoiceLatch()
        self._lock = threading.Lock()

    @property
    def total(self) -> int:
        return self._total

    @property
    def decision(self) -> ChoiceLatch:
        return self._decision

    @property
    def remaining(self) -> int:
        return self._remaining

    @property
    def result(self) -> NextEpisodeChoice | None:
        return self._decision.result

    @property
    def is_finished(self) -> bool:
        return self._decision.is_finished

    def tick(self) -> int:
        with self._lock:
            if self._decision.is_finished:
                return self._remaining
            if self._remaining <= 1:
                # remaining only drops to zero if this tick decided the timeout
                if self._decision.time_out():
                    self._remaining = 0
                return self._remaining
            self._remaining -= 1
            return self._remaining

    def confirm(self) -> bool:
        return self._decision.confirm()

    def cancel(self) -> bool:
        return self._decision.cancel()


def choice_for_action(action_id: int) -> NextEpisodeChoice | None:
    if action_id in _CANCEL_ACTIONS:
        return NextEpisodeChoice.CANCEL
    return None


def choice_for_click(control_id: int) -> NextEpisodeChoice | None:
    if control_id == NEXT_EPISODE_BUTTON_CONTINUE:
        return NextEpisodeChoice.CONTINUE
    if control_id == NEXT_EPISODE_BUTTON_CANCEL:
        return NextEpisodeChoice.CANCEL
    return None


def run_countdown_ticks(
    countdown: Countdown,
    stop_event: threading.Event,
    abort_requested: Callable[[], bool],
    show_remaining: Callable[[int], None],
    close: Callable[[], None],
    interval: float = 1.0,
) -> None:
    while not stop_event.wait(interval):
        if abort_requested():
            if countdown.cancel():
                close()
            return
        remaining = countdown.tick()
        if countdown.is_finished:
            if countdown.result is NextEpisodeChoice.TIMEOUT and not stop_event.is_set():
                close()
            return
        if stop_event.is_set():
            return
        try:
            show_remaining(remaining)
        except RuntimeError:
            pass  # control is gone once the dialog was closed


def run_abort_watch(
    latch: ChoiceLatch,
    stop_event: threading.Event,
    abort_requested: Callable[[], bool],
    close: Callable[[], None],
    interval: float = 1.0,
) -> None:
    """Closes a dialog without countdown once Kodi shuts down, unless a decision was made before."""
    while not stop_event.wait(interval):
        if abort_requested():
            if latch.cancel():
                close()
            return


def read_countdown_seconds(addon) -> int:
    try:
        value = addon.getSettingInt(COUNTDOWN_SETTING)
    except Exception:
        return DEFAULT_COUNTDOWN_SECONDS
    if not isinstance(value, int) or isinstance(value, bool):
        return DEFAULT_COUNTDOWN_SECONDS
    return min(MAX_COUNTDOWN_SECONDS, max(MIN_COUNTDOWN_SECONDS, value))
