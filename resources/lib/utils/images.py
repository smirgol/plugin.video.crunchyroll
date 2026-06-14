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

IMG_BACKDROP_WIDE = "https://imgsrv.crunchyroll.com/cdn-cgi/image/fit=cover,format=auto,quality=85,width=3840,height=2160/keyart/{crid}-backdrop_wide"
IMG_TITLE_LOGO = "https://imgsrv.crunchyroll.com/cdn-cgi/image/fit=contain,format=auto,quality=85,width=800,height=310/keyart/{crid}-title_logo-en-us"



def get_img_from_static(image, api, image_type="normal") -> str | None:
    if image is None:
        return None

    path = api.STATIC_IMG_PROFILE
    if image_type == "wallpaper":
        path = api.STATIC_WALLPAPER_PROFILE

    return path + image


def get_img_from_struct(item: dict, image_type: str, depth: int = 2) -> str | None:
    """dive into API info structure and extract requested image from its struct"""

    if item.get("images") and item.get("images").get(image_type):
        src = item.get("images").get(image_type)
        for _ in range(depth):
            if src[-1]:
                src = src[-1]
            else:
                return None
        if src.get("source"):
            return src.get("source")

    return None


def infer_img_from_id(crid: str, image_type: str) -> str | None:
    """
    Generate Crunchyroll artwork URL based on ID and image type.

    Args:
        crid: Crunchyroll series/item ID
        image_type: Type of artwork (backdrop_wide, title_logo)

    Returns:
        Generated URL or None if invalid input
    """
    if not crid:
        return None

    if image_type == "backdrop_wide":
        return IMG_BACKDROP_WIDE.format(crid=crid)
    if image_type == "title_logo":
        return IMG_TITLE_LOGO.format(crid=crid)
    return None
