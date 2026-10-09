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

"""Compact, secret-free request/response trace output for API debugging."""

from __future__ import annotations

import re
from typing import Any

MAX_TRACED_ITEMS = 20
STREAM_TOKEN_PATH = re.compile(r"(/token/[^/?#\s]+/)[^/?#\s]+")
QUERY_STRING = re.compile(r"\?\S*")
CMS_SIGNING_KEYS = frozenset({"Policy", "Signature", "Key-Pair-Id"})
METADATA_KEYS = ("episode_metadata", "series_metadata", "movie_listing_metadata", "movie_metadata")


def is_trace_enabled(args: Any) -> bool:
    """Tracing follows the addon's debug_logging setting."""
    addon = getattr(args, "addon", None)
    if addon is None:
        return False
    return addon.getSetting("debug_logging") == "true"


def redact_url(url: str) -> str:
    """Mask the stream token in /token/<content_id>/<token> paths and every query string, also inside free text."""
    return QUERY_STRING.sub("?***", STREAM_TOKEN_PATH.sub(r"\1***", url))


def redact_params(params: dict | None) -> dict:
    """Return a copy of params without CMS signing values and tokens."""
    if not params:
        return {}
    return {key: value for key, value in params.items() if key not in CMS_SIGNING_KEYS and "token" not in key.lower()}


def summarize_response(data: Any) -> str:
    """One header line plus one line per listed item (capped at MAX_TRACED_ITEMS)."""
    if data is None:
        return "<no data>"
    if not isinstance(data, dict):
        return f"<{type(data).__name__}>"

    lines = [_summarize_header(data)]
    items = _collect_items(data)
    lines.extend(_summarize_item(item) for item in items[:MAX_TRACED_ITEMS])
    if len(items) > MAX_TRACED_ITEMS:
        lines.append(f"  ... +{len(items) - MAX_TRACED_ITEMS} more")
    return "\n".join(lines)


def _summarize_header(data: dict) -> str:
    parts = [f"{key}={data[key]}" for key in ("error", "code", "total", "meta") if key in data]
    if "audioLocale" in data:
        parts.append(f"audioLocale={data['audioLocale']}")
        parts.append(f"hardSubs={_sorted_keys(data.get('hardSubs'))}")
        parts.append(f"subtitles={_sorted_keys(data.get('subtitles'))}")
        parts.append(f"url={'yes' if data.get('url') else 'no'}")
    return " ".join(parts)


def _sorted_keys(value: Any) -> str:
    keys = sorted(value) if isinstance(value, dict) else []
    return f"[{', '.join(keys)}]"


def _collect_items(data: dict) -> list:
    items = data.get("data") if isinstance(data.get("data"), list) else data.get("items")
    if not isinstance(items, list):
        return []

    # search groups its results by type, each group holding its own item list
    collected = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("items"), list):
            collected.extend(nested for nested in item["items"] if isinstance(nested, dict))
        else:
            collected.append(item)
    return collected


def _summarize_item(item: dict) -> str:
    # watchlist and history wrap the actual object in a panel
    obj = item["panel"] if isinstance(item.get("panel"), dict) else item
    metadata = next((obj[key] for key in METADATA_KEYS if isinstance(obj.get(key), dict)), {})

    def field(key: str) -> Any:
        return obj.get(key) or metadata.get(key)

    parts = [f"id={obj.get('id')}"]
    for label, key in (("type", "type"), ("audio", "audio_locale"), ("season", "season_id"), ("series", "series_id")):
        value = field(key)
        if value:
            parts.append(f"{label}={value}")

    versions = field("versions")
    if isinstance(versions, list):
        parts.append(f"versions=[{', '.join(_format_version(v) for v in versions if isinstance(v, dict))}]")
    return "  " + " ".join(parts)


def _format_version(version: dict) -> str:
    target = version.get("guid")
    if version.get("season_guid"):
        target = f"{target}/{version['season_guid']}"
    return f"{version.get('audio_locale')}:{target}"
