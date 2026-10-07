"""Tests for the declarative mode registry in resources/lib/modes.py"""

import sys
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


def test_season_wanted_dispatches_to_view_wanted_season():
    """Decision 7.8: the 'goto season' context menu of episodes resolves the wanted season at click time."""
    from resources.lib import controller

    assert MODE_REGISTRY.get("season_wanted") is controller.view_wanted_season


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


@patch("resources.lib.modes.xbmcgui")
@patch("resources.lib.modes.crunchy_log")
@patch("resources.lib.modes.show_main_menu")
def test_check_mode_unknown_logs_error_and_notifies(mock_show_main_menu, mock_crunchy_log, mock_xbmcgui, ctx):
    """An unknown (but set) mode logs an error, notifies the user, then shows the main menu.

    Mirrors the original check_mode behaviour where a set-but-unrecognised mode
    is an error condition, distinct from a missing mode.
    """
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": "not_a_real_mode",
        "id": None,
        "url": None,
    }.get(key, default)

    check_mode(ctx)

    mock_crunchy_log.assert_called_once()
    mock_xbmcgui.Dialog.return_value.notification.assert_called_once()
    mock_show_main_menu.assert_called_once_with(ctx)


@patch("resources.lib.modes.xbmcgui")
@patch("resources.lib.modes.crunchy_log")
@patch("resources.lib.modes.show_main_menu")
def test_check_mode_no_mode_routes_silently_to_main_menu(mock_show_main_menu, mock_crunchy_log, mock_xbmcgui, ctx):
    """A missing mode silently shows the main menu without logging or notifying."""
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": None,
        "id": None,
        "url": None,
    }.get(key, default)

    check_mode(ctx)

    mock_crunchy_log.assert_not_called()
    mock_xbmcgui.Dialog.return_value.notification.assert_not_called()
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


def test_mode_registry_contains_reauth():
    """'reauth' is a registered mode so a successful re-authentication lands on a known route."""
    assert "reauth" in MODE_REGISTRY


@pytest.fixture
def reauth_ctx(ctx):
    """ctx requesting mode=reauth; main-menu rendering is stubbed so it cannot touch shared Kodi stubs."""
    ctx.args.get_arg.side_effect = lambda key, default=None, _cast=None: {
        "mode": "reauth",
        "id": None,
        "url": None,
    }.get(key, default)
    ctx.args.addonurl = "plugin://plugin.video.crunchyroll"
    ctx.args.argv = ["plugin://plugin.video.crunchyroll/", "7"]
    with patch("resources.lib.crunchyroll.view") as mock_view, patch("resources.lib.crunchyroll.get_img_from_static"):
        ctx.mock_view = mock_view
        yield ctx


# xbmc/xbmcplugin are the shared stub modules from conftest; patching attributes on them works
# regardless of whether modes.py imports them at module level or lazily.
@patch.object(sys.modules["xbmcplugin"], "endOfDirectory")
def test_check_mode_reauth_closes_directory_unsuccessfully(mock_end_of_directory, reauth_ctx):
    """Mode 'reauth' closes the current listing as failed so Kodi does not keep it in history."""
    with patch.object(sys.modules["xbmc"], "executebuiltin"):
        check_mode(reauth_ctx)

    mock_end_of_directory.assert_called_once_with(handle=7, succeeded=False)


@patch.object(sys.modules["xbmc"], "executebuiltin")
def test_check_mode_reauth_redirects_to_root_replacing_history(mock_executebuiltin, reauth_ctx):
    """Mode 'reauth' is one-shot: it redirects to the addon root and replaces the history entry."""
    with patch.object(sys.modules["xbmcplugin"], "endOfDirectory"):
        check_mode(reauth_ctx)

    mock_executebuiltin.assert_called_once_with("Container.Update(plugin://plugin.video.crunchyroll/,replace)")


@patch("resources.lib.modes.xbmcgui")
@patch("resources.lib.modes.crunchy_log")
def test_check_mode_reauth_renders_nothing_and_reports_no_error(mock_crunchy_log, mock_xbmcgui, reauth_ctx):
    """Mode 'reauth' renders no menu items, raises no unknown-mode error and leaves args untouched."""
    with patch.object(sys.modules["xbmcplugin"], "endOfDirectory"), patch.object(sys.modules["xbmc"], "executebuiltin"):
        check_mode(reauth_ctx)

    reauth_ctx.mock_view.add_item.assert_not_called()
    mock_crunchy_log.assert_not_called()
    mock_xbmcgui.Dialog.return_value.notification.assert_not_called()
    reauth_ctx.args.set_arg.assert_not_called()
