# Crunchyroll
# Copyright (C) 2023 smirgol
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

"""Compatibility facade for the old `resources.lib.model` module.

The actual model classes have moved to `resources.lib.models`. Import from
`resources.lib.models` directly in new code; this facade only exists so
existing code and external tests keep working during the phased refactor.
"""

__all__ = [
    "Args",
    "CMS",
    "AccountData",
    "ProfileData",
    "Cacheable",
    "ListableItem",
    "Meta",
    "Object",
    "PlayableItem",
    "EpisodeData",
    "MovieData",
    "SeasonData",
    "SeriesData",
    "CrunchyrollError",
    "LoginError",
]

from .account import CMS as CMS
from .account import AccountData as AccountData
from .account import ProfileData as ProfileData
from .args import Args as Args
from .base import Cacheable as Cacheable
from .base import ListableItem as ListableItem
from .base import Meta as Meta
from .base import Object as Object
from .base import PlayableItem as PlayableItem
from .content import EpisodeData as EpisodeData
from .content import MovieData as MovieData
from .content import SeasonData as SeasonData
from .content import SeriesData as SeriesData
from .exceptions import CrunchyrollError as CrunchyrollError
from .exceptions import LoginError as LoginError
