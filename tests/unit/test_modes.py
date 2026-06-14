"""Tests for the declarative mode registry in resources/lib/modes.py"""

from unittest.mock import MagicMock, patch

import pytest

from resources.lib.context import PluginContext
from resources.lib.modes import MODE_REGISTRY, check_mode, derive_mode_from_args


@pytest.fixture
def ctx():
    """Provide a PluginContext with a mock args that supports get_arg/set_arg."""
    mock_args = MagicMock()
    mock_args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": None,
        "id": None,
        "url": None,
    }.get(key, default)
    mock_args.set_arg = MagicMock()
    mock_args.argv = ["plugin://plugin.video.crunchyroll/", "1"]
    mock_api = MagicMock()
    mock_monitor = MagicMock()
    return PluginContext(api=mock_api, args=mock_args, monitor=mock_monitor)


def test_mode_registry_contains_expected_modes():
    """Every documented mode from the legacy if/elif chain is in the registry."""
    expected = {
        "queue",
        "search",
        "history",
        "resume",
        "anime",
        "drama",
        "popular",
        "newest",
        "alpha",
        "season",
        "genre",
        "seasons",
        "episodes",
        "videoplay",
        "add_to_queue",
        "crunchylists_lists",
        "crunchylists_item",
        "profiles_list",
    }
    assert expected.issubset(set(MODE_REGISTRY.keys()))


def test_mode_registry_values_are_callable():
    """Each registry value must accept a PluginContext and be callable."""
    for mode, handler in MODE_REGISTRY.items():
        assert callable(handler), f"Handler for mode {mode!r} is not callable"


def test_derive_mode_from_args_id(ctx):
    """derive_mode_from_args returns videoplay and mutates url when id is present."""
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": None,
        "id": "12345",
        "url": None,
    }.get(key, default)

    mode = derive_mode_from_args(ctx.args)

    assert mode == "videoplay"
    ctx.args.set_arg.assert_called_once_with("url", "/media-12345")


def test_derive_mode_from_args_url(ctx):
    """derive_mode_from_args returns videoplay and truncates url when url is present."""
    long_url = "https://www.crunchyroll.com/watch/media-12345/slug"
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": None,
        "id": None,
        "url": long_url,
    }.get(key, default)

    mode = derive_mode_from_args(ctx.args)

    assert mode == "videoplay"
    ctx.args.set_arg.assert_called_once_with("url", long_url[26:])


def test_derive_mode_from_args_no_args(ctx):
    """derive_mode_from_args returns None when no routing arguments are set."""
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": None,
        "id": None,
        "url": None,
    }.get(key, default)

    assert derive_mode_from_args(ctx.args) is None


@patch("resources.lib.modes.show_main_menu")
def test_check_mode_unknown_falls_back_to_main_menu(mock_show_main_menu, ctx):
    """An unknown mode routes to show_main_menu."""
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": "not_a_real_mode",
        "id": None,
        "url": None,
    }.get(key, default)

    check_mode(ctx)

    mock_show_main_menu.assert_called_once_with(ctx)


@patch("resources.lib.modes.show_main_menu")
def test_check_mode_no_mode_routes_to_main_menu(mock_show_main_menu, ctx):
    """Missing mode routes to show_main_menu."""
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": None,
        "id": None,
        "url": None,
    }.get(key, default)

    check_mode(ctx)

    mock_show_main_menu.assert_called_once_with(ctx)


@patch("resources.lib.modes.MODE_REGISTRY")
def test_check_mode_dispatches_registered_mode(mock_registry, ctx):
    """check_mode looks up the mode in the registry and calls it with ctx."""
    handler = MagicMock(return_value=True)
    mock_registry.get.return_value = handler
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": "queue",
        "id": None,
        "url": None,
    }.get(key, default)

    result = check_mode(ctx)

    assert result is True
    handler.assert_called_once_with(ctx)


@patch("resources.lib.crunchyroll.show_main_category")
def test_check_mode_anime_routes_to_show_main_category(mock_show_main_category, ctx):
    """Mode 'anime' passes the genre argument to show_main_category."""
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": "anime",
        "id": None,
        "url": None,
    }.get(key, default)

    check_mode(ctx)

    mock_show_main_category.assert_called_once_with(ctx, "anime")


@patch("resources.lib.crunchyroll.show_main_category")
def test_check_mode_drama_routes_to_show_main_category(mock_show_main_category, ctx):
    """Mode 'drama' passes the genre argument to show_main_category."""
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": "drama",
        "id": None,
        "url": None,
    }.get(key, default)

    check_mode(ctx)

    mock_show_main_category.assert_called_once_with(ctx, "drama")
