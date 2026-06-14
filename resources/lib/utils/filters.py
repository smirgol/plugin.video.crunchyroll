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

from ..globals import G


def _filter_by_locales(panel: dict, audio_locales: list, subtitle_locales: list | None = None) -> bool:
    """Shared locale matching logic for series and seasons."""

    if G.args.addon.getSetting("filter_dubs_by_language") != "true":
        return True

    # main audio language
    if G.args.addon.getSetting("show_dubs_by_language") == "true":
        if G.args.subtitle in audio_locales:
            return True

    # fallback audio language
    if (
        G.args.addon.getSetting("show_dubs_by_language_fallback") == "true"
        and G.args.subtitle_fallback
        and G.args.subtitle_fallback in audio_locales
    ):
        return True

    if G.args.addon.getSetting("show_subs_by_language") == "true":
        # edge case for chinese only anime where there is no japanese dub
        # @see: https://github.com/smirgol/plugin.video.crunchyroll/issues/51
        if "ja-JP" in audio_locales or "zh-CN" in audio_locales:
            if subtitle_locales == [] and panel.get("is_subbed", False) is True:
                return True

            if subtitle_locales and G.args.subtitle in subtitle_locales:
                return True

            if subtitle_locales and G.args.subtitle_fallback and G.args.subtitle_fallback in subtitle_locales:
                return True

    return False


def filter_series(seriesItem: dict) -> bool:
    """takes an API info struct and returns if it matches user language settings"""

    panel = seriesItem.get("panel") or seriesItem
    item = panel.get("series_metadata") or panel

    return _filter_by_locales(
        panel,
        item.get("audio_locales", []),
        item.get("subtitle_locales", []),
    )


def filter_seasons(item: dict) -> bool:
    """takes an API info struct and returns if it matches user language settings"""

    return _filter_by_locales(
        item,
        [item.get("audio_locale", "")],
        item.get("subtitle_locales", []),
    )
