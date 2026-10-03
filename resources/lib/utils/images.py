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

from enum import Enum


class ImageType(Enum):
    """Known Crunchyroll image type identifiers."""

    POSTER_TALL = "poster_tall"
    POSTER_WIDE = "poster_wide"
    THUMBNAIL = "thumbnail"
    BACKDROP_WIDE = "backdrop_wide"
    TITLE_LOGO = "title_logo"
    NORMAL = "normal"
    WALLPAPER = "wallpaper"


IMG_BACKDROP_WIDE = "https://imgsrv.crunchyroll.com/cdn-cgi/image/fit=cover,format=auto,quality=85,width=3840,height=2160/keyart/{crid}-backdrop_wide"
IMG_TITLE_LOGO = "https://imgsrv.crunchyroll.com/cdn-cgi/image/fit=contain,format=auto,quality=85,width=800,height=310/keyart/{crid}-title_logo-en-us"

STATIC_IMG_PROFILE = "https://static.crunchyroll.com/assets/avatar/170x170/"
STATIC_WALLPAPER_PROFILE = "https://static.crunchyroll.com/assets/wallpaper/720x180/"


def get_img_from_static(image, image_type: ImageType = ImageType.NORMAL) -> str | None:
    if image is None:
        return None

    path = STATIC_WALLPAPER_PROFILE if image_type == ImageType.WALLPAPER else STATIC_IMG_PROFILE

    return path + image


def get_img_from_struct(item: dict, image_type: ImageType, depth: int = 2) -> str | None:
    """dive into API info structure and extract requested image from its struct"""

    key = image_type.value if isinstance(image_type, ImageType) else image_type
    if item.get("images") and item.get("images").get(key):
        src = item.get("images").get(key)
        for _ in range(depth):
            if src[-1]:
                src = src[-1]
            else:
                return None
        if src.get("source"):
            return src.get("source")

    return None


def infer_img_from_id(crid: str, image_type: ImageType) -> str | None:
    """
    Generate Crunchyroll artwork URL based on ID and image type.

    Args:
        crid: Crunchyroll series/item ID
        image_type: Type of artwork

    Returns:
        Generated URL or None if invalid input
    """
    if not crid:
        return None

    if image_type == ImageType.BACKDROP_WIDE:
        return IMG_BACKDROP_WIDE.format(crid=crid)
    if image_type == ImageType.TITLE_LOGO:
        return IMG_TITLE_LOGO.format(crid=crid)
    return None
