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

from datetime import datetime

from ..models import EpisodeData, ListableItem, MovieData
from . import logging


def format_long_episode_title(season_title: str, series_number: int, episode_number: int, title: str) -> str:
    series_number_str = str(series_number)
    episode_number_str = str(episode_number)

    return season_title + " - S" + f"{series_number_str:0>2}" + "E" + f"{episode_number_str:0>2}" + " - " + title


def format_short_episode_title(episode_number: int, title: str) -> str:
    return two_digits(episode_number) + " - " + title


def two_digits(n: int) -> str:
    if not n:
        return "00"
    if n < 10:
        return "0" + str(n)
    return str(n)


def convert_text_to_date(date_str) -> datetime:
    return datetime.strptime(date_str, "%Y-%m-%d")


def sort_episodes(listables: list[ListableItem]) -> list[ListableItem]:
    """Sort episodes list to move all unwatched episodes to top"""

    watched = []
    unwatched = []

    for listable in listables:
        if not isinstance(listable, EpisodeData) and not isinstance(listable, MovieData):
            logging.crunchy_log("Error sorting episodes. Not an episode nor movie")
            continue

        if listable.playcount == 1:
            watched.append(listable)
        else:
            unwatched.append(listable)

    watched.sort(key=lambda obj: convert_text_to_date(obj.aired), reverse=True)
    unwatched.sort(key=lambda obj: convert_text_to_date(obj.aired), reverse=True)

    return unwatched + watched
