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


_FALLBACK_ORIGINAL_LOCALES = ("ja-JP", "zh-CN")


def season_versions(item: dict) -> list[dict]:
    """Return one shallow copy of a season item per entry in its ``versions``.

    Without versions the item itself is the only variant; it counts as original for ja-JP / zh-CN audio.
    """

    versions = item.get("versions")
    if not versions:
        return [{**item, "original": item.get("audio_locale") in _FALLBACK_ORIGINAL_LOCALES}]

    return [
        {
            **item,
            "id": version["guid"],
            "audio_locale": version["audio_locale"],
            "original": bool(version.get("original")),
        }
        for version in versions
    ]


def has_wanted_subtitles(subtitle_locales: list | None, is_subbed: bool, prefs: LanguagePreferences) -> bool:
    """Whether the subtitles contain the primary or fallback language."""

    # edge case for chinese only anime that carry no subtitle locales
    # @see: https://github.com/smirgol/plugin.video.crunchyroll/issues/51
    if subtitle_locales == [] and is_subbed is True:
        return True

    if not subtitle_locales:
        return False

    if prefs.subtitle in subtitle_locales:
        return True

    return bool(prefs.subtitle_fallback) and prefs.subtitle_fallback in subtitle_locales


def is_version_wanted(variant: dict, prefs: LanguagePreferences) -> bool:
    """Whether a season variant matches the language filter."""

    if not prefs.filter_enabled:
        return True

    audio_locale = variant.get("audio_locale")

    if prefs.show_dubs and audio_locale == prefs.subtitle:
        return True

    if prefs.show_dubs_fallback and prefs.subtitle_fallback and audio_locale == prefs.subtitle_fallback:
        return True

    return (
        prefs.show_subs
        and variant["original"]
        and has_wanted_subtitles(variant.get("subtitle_locales", []), variant.get("is_subbed", False), prefs)
    )


def order_versions(variants: list[dict], prefs: LanguagePreferences) -> list[dict]:
    """Original first, then primary dub, then fallback dub, then the rest by audio locale."""

    def sort_key(variant: dict) -> tuple:
        audio_locale = variant.get("audio_locale") or ""
        if variant.get("original"):
            return 0, ""
        if audio_locale == prefs.subtitle:
            return 1, ""
        if prefs.subtitle_fallback and audio_locale == prefs.subtitle_fallback:
            return 2, ""
        return 3, audio_locale

    return sorted(variants, key=sort_key)


def locale_code(locale: str) -> str:
    """Short upper-case code of a locale: its region if alphabetic (``de-DE`` -> ``DE``), else the whole locale."""

    _, _, region = locale.partition("-")
    if region.isalpha():
        return region.upper()
    return locale.upper()


def version_label(variant: dict, prefs: LanguagePreferences) -> str:
    """Bracketed language label of a variant, e.g. ``[JP Audio | DE Sub]`` or ``[DE Audio]``."""

    audio = f"{locale_code(variant['audio_locale'])} Audio"
    if not variant.get("original"):
        return f"[{audio}]"

    subtitle_locales = variant.get("subtitle_locales") or []
    if prefs.subtitle in subtitle_locales:
        subtitle = prefs.subtitle
    elif prefs.subtitle_fallback and prefs.subtitle_fallback in subtitle_locales:
        subtitle = prefs.subtitle_fallback
    else:
        return f"[{audio}]"

    return f"[{audio} | {locale_code(subtitle)} Sub]"


def select_season_versions(items: list[dict] | None, prefs: LanguagePreferences) -> list[dict]:
    """Wanted, ordered season variants in API season order; labelled when a season shows several."""

    selected = []
    for item in items or []:
        variants = order_versions([v for v in season_versions(item) if is_version_wanted(v, prefs)], prefs)
        if len(variants) > 1:
            for variant in variants:
                variant["title"] = f"{variant.get('title', '')} {version_label(variant, prefs)}"
        selected.extend(variants)

    return selected
