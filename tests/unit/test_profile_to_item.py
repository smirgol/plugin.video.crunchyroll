"""Regression tests for ProfileData.to_item and controller.show_profiles.

Covers the contract between resources.lib.models.account.ProfileData and
resources.lib.controller.show_profiles: ProfileData.to_item must accept the
optional `addon` argument defined by ListableItem.to_item, and show_profiles
must be able to build a selectable list from a mocked API response.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import xbmcgui

from resources.lib.controller import show_profiles
from resources.lib.models.account import ProfileData
from resources.lib.utils.images import (
    STATIC_IMG_PROFILE,
    STATIC_WALLPAPER_PROFILE,
    ImageType,
    get_img_from_static,
)


class TestProfileDataToItem:
    """ProfileData must honour the ListableItem.to_item(addon) contract."""

    def test_to_item_accepts_optional_addon(self):
        """Calling to_item(addon) must not raise TypeError."""
        profile = ProfileData({
            "profile_id": "p1",
            "profile_name": "Marco",
            "username": "marco",
            "avatar": "avatar.jpg",
        })
        addon = MagicMock()
        addon.getSetting.return_value = "false"

        # This used to raise:
        # TypeError: to_item() takes 1 positional argument but 2 were given
        item = profile.to_item(addon)
        assert item is not None

    def test_to_item_works_without_addon(self):
        """Calling to_item() without arguments must still work."""
        profile = ProfileData({
            "profile_id": "p1",
            "profile_name": "Marco",
            "username": "marco",
            "avatar": "avatar.jpg",
        })

        item = profile.to_item()
        assert item is not None

    def test_to_item_uses_profile_name_and_username(self):
        """The returned ListItem carries the profile name and username."""
        xbmcgui.ListItem.reset_mock()
        profile = ProfileData({
            "profile_id": "p1",
            "profile_name": "Marco",
            "username": "marco",
            "avatar": "avatar.jpg",
        })

        profile.to_item()
        # xbmcgui.ListItem is mocked globally; inspect the constructor call.
        assert xbmcgui.ListItem.call_args.kwargs["label"] == "Marco"
        assert xbmcgui.ListItem.call_args.kwargs["label2"] == "marco"

    def test_to_item_builds_avatar_urls(self):
        """ProfileData builds avatar URLs using the static image helper."""
        xbmcgui.ListItem.reset_mock()
        profile = ProfileData({
            "profile_id": "p1",
            "profile_name": "Marco",
            "username": "marco",
            "avatar": "avatar.jpg",
        })

        profile.to_item()
        set_art_calls = [
            call for call in xbmcgui.ListItem.return_value.method_calls
            if call[0] == "setArt"
        ]
        assert len(set_art_calls) == 1
        artworks = set_art_calls[0][1][0]
        assert artworks["thumb"] == STATIC_IMG_PROFILE + "avatar.jpg"
        assert artworks["fanart"] == STATIC_IMG_PROFILE + "avatar.jpg"
        assert artworks["poster"] == STATIC_IMG_PROFILE + "avatar.jpg"

    def test_to_item_wallpaper_uses_wallpaper_profile(self):
        """The static helper supports a dedicated wallpaper image type."""
        assert get_img_from_static("wallpaper.jpg", ImageType.WALLPAPER) == STATIC_WALLPAPER_PROFILE + "wallpaper.jpg"


class TestShowProfiles:
    """Controller.show_profiles must build a profile selection dialog."""

    def test_show_profiles_builds_list_items(self, ctx):
        """Given a profile list response, show_profiles calls xbmcgui.Dialog().select."""
        ctx.api.make_request.return_value = {
            "profiles": [
                {
                    "profile_id": "p1",
                    "profile_name": "Marco",
                    "username": "marco",
                    "avatar": "avatar1.jpg",
                },
                {
                    "profile_id": "p2",
                    "profile_name": "Kids",
                    "username": "kids",
                    "avatar": "avatar2.jpg",
                },
            ],
        }
        ctx.api.profile_data.profile_id = "p1"

        with patch("resources.lib.controller.xbmcgui.Dialog") as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.select.return_value = 0
            mock_dialog_cls.return_value = mock_dialog

            result = show_profiles(ctx)

        assert result is True
        ctx.api.make_request.assert_called_once_with(
            method="GET",
            url=ctx.api.PROFILES_LIST_ENDPOINT,
        )
        mock_dialog.select.assert_called_once()
        # Two profiles should have produced two list items.
        list_items = mock_dialog.select.call_args[0][1]
        assert len(list_items) == 2

    def test_show_profiles_returns_early_on_error_response(self, ctx):
        """If the API response is an error, render_error_directory is used."""
        ctx.api.make_request.return_value = {"error": True}

        with patch("resources.lib.controller.is_response_error", return_value=True), \
             patch("resources.lib.controller.render_error_directory") as mock_render:
            result = show_profiles(ctx)

        mock_render.assert_called_once_with(ctx)
        # show_profiles returns whatever render_error_directory returns.
        assert result is mock_render.return_value

    def test_show_profiles_cancels_on_dialog_cancel(self, ctx):
        """When the user cancels the dialog, show_profiles returns True without refreshing."""
        ctx.api.make_request.return_value = {
            "profiles": [
                {
                    "profile_id": "p1",
                    "profile_name": "Marco",
                    "username": "marco",
                    "avatar": "avatar1.jpg",
                },
            ],
        }
        ctx.api.profile_data.profile_id = ""

        with patch("resources.lib.controller.xbmcgui.Dialog") as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.select.return_value = -1
            mock_dialog_cls.return_value = mock_dialog

            result = show_profiles(ctx)

        assert result is True
        ctx.api.create_session.assert_not_called()

    def test_show_profiles_refreshes_profile_on_selection(self, ctx):
        """Selecting a profile calls create_session with the chosen profile_id."""
        ctx.api.make_request.return_value = {
            "profiles": [
                {
                    "profile_id": "p2",
                    "profile_name": "Kids",
                    "username": "kids",
                    "avatar": "avatar2.jpg",
                },
            ],
        }
        ctx.api.profile_data.profile_id = ""

        with patch("resources.lib.controller.xbmcgui.Dialog") as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.select.return_value = 0
            mock_dialog_cls.return_value = mock_dialog

            result = show_profiles(ctx)

        assert result is True
        ctx.api.create_session.assert_called_once_with(
            action="refresh_profile",
            profile_id="p2",
        )
