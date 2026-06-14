# Crunchyroll
# Copyright (C) 2023 smirgol
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

from __future__ import annotations

import xbmcgui

from .base import Cacheable, ListableItem, Object


class CMS(Object):
    def __init__(self, data: dict):
        self.bucket: str = data.get("bucket")
        self.policy: str = data.get("policy")
        self.signature: str = data.get("signature")
        self.key_pair_id: str = data.get("key_pair_id")


class AccountData(Cacheable):
    def __init__(self, data: dict):
        super().__init__()
        self.access_token: str = data.get("access_token")
        self.refresh_token: str = data.get("refresh_token")
        self.expires: str = data.get("expires")
        self.token_type: str = data.get("token_type")
        self.scope: str = data.get("scope")
        self.country: str = data.get("country")
        self.account_id: str = data.get("account_id")
        self.cms: CMS = CMS(data.get("cms", {}))
        self.service_available: bool = data.get("service_available")
        self.avatar: str = data.get("avatar")
        self.has_beta: bool = self._read(data, "cr_beta_opt_in", "has_beta")
        self.email_verified: bool = self._read(data, "crleg_email_verified", "email_verified")
        self.email: str = data.get("email")
        self.maturity_rating: str = data.get("maturity_rating")
        self.account_language: str = self._read(data, "preferred_communication_language", "account_language")
        self.default_subtitles_language: str = self._read(
            data, "preferred_content_subtitle_language", "default_subtitles_language"
        )
        self.default_audio_language: str = self._read(
            data, "preferred_content_audio_language", "default_audio_language"
        )
        self.username: str = data.get("username")

    def get_cache_file_name(self) -> str:
        return "session_data.json"


# @todo: rethink Cacheable inheritance, it's too easy to use the wrong class' properties
class ProfileData(ListableItem, Cacheable):
    def __init__(self, data: dict):
        super(ListableItem, self).__init__()
        Cacheable.__init__(self)

        self.profile_id: str = data.get("profile_id")
        self.username: str = data.get("username")
        self.profile_name: str = data.get("profile_name")

        self.account_language: str = self._read(data, "preferred_communication_language", "account_language")
        self.default_subtitles_language: str = self._read(
            data, "preferred_content_subtitle_language", "default_subtitles_language"
        )
        self.default_audio_language: str = self._read(
            data, "preferred_content_audio_language", "default_audio_language"
        )

        self.avatar: str = data.get("avatar")
        self.wallpaper: str = data.get("wallpaper")

    def get_cache_file_name(self) -> str:
        return "profile_data.json"

    def get_info(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "title": self.profile_name,
            "mode": "profiles_list_with_id",
        }

    def to_item(self) -> xbmcgui.ListItem:
        """Convert ourselves to a Kodi ListItem"""

        from .. import utils

        li = xbmcgui.ListItem(label=self.profile_name, label2=self.username)
        li.setArt(
            {
                "thumb": utils.get_img_from_static(self.avatar),
                "fanart": utils.get_img_from_static(self.avatar),
                "poster": utils.get_img_from_static(self.avatar),
                # 'fanart': utils.get_img_from_static(self.wallpaper, "wallpaper"),
                # 'poster': utils.get_img_from_static(self.wallpaper, "wallpaper")
            }
        )

        return li
