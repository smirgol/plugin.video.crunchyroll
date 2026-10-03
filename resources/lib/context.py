# Crunchyroll
# Copyright (C) 2024 smirgol
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

"""PluginContext replaces the mutable global singleton G with explicit parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import xbmc

    from .api import API
    from .models import Args


@dataclass
class PluginContext:
    """Explicit dependency container for the addon.

    Holds api, args, and monitor so controllers and views can receive them as
    parameters instead of importing the G singleton.
    """

    api: API
    args: Args
    monitor: xbmc.Monitor
