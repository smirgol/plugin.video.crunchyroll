"""Safe controller helper functions.

Family of small helpers (not one-size-fits-all) to DRY error and
pagination blocks in controller.py while preserving exact semantics.
"""

from __future__ import annotations

from . import view
from .context import PluginContext


def is_response_error(req: dict | None) -> bool:
    """True if *req* is falsy or contains the key ``"error"``.

    Covers the most common controller variant:
    ``if not req or "error" in req:``
    """
    return not req or "error" in req


def is_response_error_strict(req: dict | None) -> bool:
    """True if *req* is ``None`` or ``req.get("error") is not None``.

    Covers the stricter controller variants used where *req* is expected
    to be a dict (e.g. ``list_seasonal_tags``, ``list_categories``).
    """
    return req is None or req.get("error") is not None


def render_error_directory(ctx: PluginContext, title_id: int = 30061) -> bool:
    """Add a single error item, end the directory, and return ``False``.

    Matches the repeated copy-pasta in every list-view function.
    """
    view.add_item(ctx, {"title": ctx.args.addon.getLocalizedString(title_id)})
    view.end_of_directory(ctx)
    return False


def add_next_page_item(ctx: PluginContext, offset: int = 0, mode: str = "", **extra_params) -> None:
    """Add a "Next page" pagination item (localized string 30044).

    Parameters are merged into the item dict exactly like the original
    manual blocks.
    """
    item: dict[str, object] = {
        "title": ctx.args.addon.getLocalizedString(30044),
        "offset": offset,
        "mode": mode,
    }
    item.update(extra_params)
    view.add_item(ctx, item, is_folder=True)
