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

"""Shared datetime helpers used across the addon."""

from __future__ import annotations

import time
from datetime import datetime


def get_date() -> datetime:
    """Return current UTC time."""
    return datetime.utcnow()


def date_to_str(date: datetime) -> str:
    """Serialize a datetime as the addon's canonical string format."""
    return f"{date.year}-{date.month}-{date.day}T{date.hour}:{date.minute}:{date.second}Z"


def str_to_date(string: str) -> datetime:
    """Parse a canonical-format datetime string."""
    time_format = "%Y-%m-%dT%H:%M:%SZ"

    try:
        res = datetime.strptime(string, time_format)
    except TypeError:
        res = datetime(*(time.strptime(string, time_format)[0:6]))

    return res
