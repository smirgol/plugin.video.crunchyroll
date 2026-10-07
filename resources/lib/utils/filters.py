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

from .language import LanguagePreferences, has_wanted_subtitles


def _filter_by_locales(
    panel: dict,
    audio_locales: list,
    subtitle_locales: list | None,
    prefs: LanguagePreferences,
) -> bool:
    """Locale matching logic for series."""

    if not prefs.filter_enabled:
        return True

    # main audio language
    if prefs.show_dubs:
        if prefs.subtitle in audio_locales:
            return True

    # fallback audio language
    if prefs.show_dubs_fallback and prefs.subtitle_fallback and prefs.subtitle_fallback in audio_locales:
        return True

    if prefs.show_subs:
        # edge case for chinese only anime where there is no japanese dub
        # @see: https://github.com/smirgol/plugin.video.crunchyroll/issues/51
        if "ja-JP" in audio_locales or "zh-CN" in audio_locales:
            if has_wanted_subtitles(subtitle_locales, panel.get("is_subbed", False), prefs):
                return True

    return False


def filter_series(seriesItem: dict, args) -> bool:
    """takes an API info struct and returns if it matches user language settings"""

    panel = seriesItem.get("panel") or seriesItem
    item = panel.get("series_metadata") or panel

    return _filter_by_locales(
        panel,
        item.get("audio_locales", []),
        item.get("subtitle_locales", []),
        LanguagePreferences.from_args(args),
    )
