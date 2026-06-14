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

"""Backward-compatibility facade for the refactored utils package.

All implementation has moved to resources.lib.utils.{api_data,images,formatting,filters,logging}.
New code should import directly from the submodules; this module is retained during the transition
and will be removed in Phase 9a.
"""

from __future__ import annotations

from .utils import *  # noqa: F401,F403
