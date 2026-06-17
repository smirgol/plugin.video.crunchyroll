# Crunchyroll
# Copyright (C) 2023 smirgol
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

from __future__ import annotations

import re
import sys
from typing import Any

try:
    from urllib import unquote_plus
except ImportError:
    from urllib.parse import unquote_plus

import xbmcaddon

from resources.lib import router


class Args:
    """Arguments class
    Hold all arguments passed to the script and also persistent user data and
    reference to the addon. It is intended to hold all data necessary for the
    script.
    """

    @classmethod
    def from_argv(cls, argv):
        """Create an Args instance from Kodi's sys.argv."""
        try:
            from urlparse import parse_qs
        except ImportError:
            from urllib.parse import parse_qs

        if argv[2]:
            return cls(argv, parse_qs(argv[2][1:]))
        return cls(argv, {})

    def __init__(self, argv, kwargs):
        """Initialize arguments object
        Hold also references to the addon which can't be kept at module level.
        """
        # addon specific data
        self.PY2 = sys.version_info[0] == 2  #: True for Python 2
        self._argv: list = argv
        self._addonurl = re.sub(r"^(plugin://[^/]+)/.*$", r"\1", argv[0])
        self._addonid = self._addonurl[9:]
        self._addon = xbmcaddon.Addon(id=self._addonid)
        self._addonname = self._addon.getAddonInfo("name")
        self._cj = None
        self._device_id = None
        self._args: dict = {}  # holds all parameters provided via URL
        # data from settings
        self._subtitle = None
        self._subtitle_fallback = None

        self._url = re.sub(r"plugin://[^/]+/", "/", argv[0])

        route_params = router.extract_url_params(self._url)

        if route_params is not None:
            for key, value in route_params.items():
                if value:
                    self._args[key] = unquote_plus(value)

        for key, value in kwargs.items():
            if value:
                self._args[key] = unquote_plus(value[0])

    def get_arg(self, arg: str, default: Any = None, cast: type = None):
        """Get an argument provided via URL"""
        value = self._args.get(arg, default)
        if cast:
            value = cast(value)
        return value

    def set_arg(self, key: str, value=Any):
        self._args[key] = value

    def set_args(self, data: dict | dict | list):
        self._args.update(data)

    @property
    def addon(self):
        return self._addon

    @property
    def addon_name(self):
        return self._addonname

    @property
    def addon_id(self):
        return self._addonid

    @property
    def addonurl(self):
        return self._addonurl

    @property
    def argv(self):
        return self._argv

    @property
    def device_id(self):
        return self._device_id

    @property
    def subtitle(self):
        return self._subtitle

    @property
    def subtitle_fallback(self):
        return self._subtitle_fallback

    @property
    def args(self):
        return self._args

    @property
    def url(self):
        return self._url
