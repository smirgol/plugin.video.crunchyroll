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

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguagePreferences:
    """User language and language-filter preferences."""

    subtitle: str | None
    subtitle_fallback: str | None
    filter_enabled: bool
    show_dubs: bool
    show_dubs_fallback: bool
    show_subs: bool

    @classmethod
    def from_args(cls, args) -> LanguagePreferences:
        """Build preferences from the plugin args and their addon settings."""

        return cls(
            subtitle=args.subtitle,
            subtitle_fallback=args.subtitle_fallback,
            filter_enabled=args.addon.getSetting("filter_dubs_by_language") == "true",
            show_dubs=args.addon.getSetting("show_dubs_by_language") == "true",
            show_dubs_fallback=args.addon.getSetting("show_dubs_by_language_fallback") == "true",
            show_subs=args.addon.getSetting("show_subs_by_language") == "true",
        )
