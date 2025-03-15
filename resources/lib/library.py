# -*- coding: utf-8 -*-
# Crunchyroll
# Copyright (C) 2025 gigoro33
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

import json
import xbmc
import xbmcgui
import xbmcvfs

from . import utils
from .globals import G
import xmltodict

def get_info_series():
    # api request
    req = G.api.make_request(
        method="GET",
        url=G.api.SERIES_ENDPOINT.format(G.args.get_arg('series_id')),
        params={
            "locale": G.args.subtitle,
            "preferred_audio_language": G.api.account_data.default_audio_language
        }
    )
    
    # check for error
    if not req or "error" in req:
        return None
    
    
    return req
def get_info_season():
    """ get information all seasons/arcs of an anime
    """
    # api request
    req = G.api.make_request(
        method="GET",
        url=G.api.SEASONS_ENDPOINT.format(G.api.account_data.cms.bucket),
        params={
            "locale": G.args.subtitle,
            "series_id": G.args.get_arg('series_id'),
            "preferred_audio_language": G.api.account_data.default_audio_language,
            "force_locale": ""
        }
    )

    # check for error
    if not req or "error" in req:
        return None

    return req

def get_info_episodes(season_id):
    """ get all episodes of season
    """
    # api request
    req = G.api.make_request(
        method="GET",
        url=G.api.EPISODES_ENDPOINT.format(G.api.account_data.cms.bucket),
        params={
            "locale": G.args.subtitle,
            "season_id": season_id
        }
    )

    # check for error
    if not req or "error" in req:
        return None

    return req

def add_series_library():
    # Initialize progress dialog
    pDialog = xbmcgui.DialogProgress()
    pDialog.create("Processing...", "Getting information from the series")
    series = get_info_series()
    
    # check for error
    if series == None:
        pDialog.close()

        xbmcgui.Dialog().notification(
            G.args.addon_name,
            G.args.addon.getLocalizedString(30061),
            xbmcgui.NOTIFICATION_ERROR
        )
        return False
        
    # write file content    
    file_path_tv_show = f"special://profile/addon_data/plugin.video.crunchyroll/video-library/crunchyroll-tv-shows/{series['data'][0]['slug_title']}"
    
    if not xbmcvfs.exists(file_path_tv_show):
        xbmcvfs.mkdir(file_path_tv_show)

    poster_tall_images = series["data"][0]["images"]["poster_tall"][0]
    poster_tall_images = max(poster_tall_images, key=lambda x: x["width"])
    
    poster_wide_images = series["data"][0]["images"]["poster_wide"][0]
    poster_wide_images = max(poster_wide_images, key=lambda x: x["width"])
    
    tv_show = {
        "tvshow": {
            "title": series["data"][0]["title"],
            "plot": series["data"][0]["description"],
            "thumb": [
                {
                    "@aspect": "poster",
                    "#text": poster_tall_images["source"]
                },
                {
                    "@aspect": "banner",
                    "#text": poster_wide_images["source"]
                }
            ],
            "episode": series["data"][0]["episode_count"],
            "season": series["data"][0]["season_count"],
            "namedseason": [],
        }
    }
    
    with xbmcvfs.File(f"{file_path_tv_show}/tvshow.nfo", 'w') as f:
        f.write(xmltodict.unparse(tv_show, pretty=True))
    
    seasons = get_info_season()
    total_seasons = len(seasons["items"])
    
    for ids, s in enumerate(seasons["items"]):
        # filter series items based on language settings
        if not utils.filter_seasons(s):
            continue
        
        # add season name
        tv_show["tvshow"]["namedseason"].append({
            "@number": s["season_number"],
            "#text": s["title"]
        })
        
        with xbmcvfs.File(f"{file_path_tv_show}/tvshow.nfo", 'w') as f:
            f.write(xmltodict.unparse(tv_show, pretty=True))
        
        # get episodes information    
        episodes = get_info_episodes(s["id"])
        percent = int(((ids + 1) / total_seasons) * 100)  # Ensuring 100% on last season
    
        for e in episodes['items']:
            pDialog.update(percent, f"Processing Season Episodes: {ids + 1} of {total_seasons}:\n {e['title']}")
            
            item_type = e.get('panel', {}).get('type') or e.get('type') or e.get('__class__')
            
            if item_type == 'movie' or e["episode_number"] == None:
                # create folder movie    
                file_path_movies = f"special://profile/addon_data/plugin.video.crunchyroll/video-library/crunchyroll-movies/{e['slug_title']}"
                
                if not xbmcvfs.exists(file_path_movies):
                    xbmcvfs.mkdir(file_path_movies)
                    
                # create strm file for movie
                file_name = f"{file_path_movies}/{e['title']}"
                panel = e.get('panel') or e
                stream = utils.get_stream_id_from_item(panel)
                
                with xbmcvfs.File(f"{file_name}.strm", 'w') as f:
                    f.write(f"plugin://plugin.video.crunchyroll/video/{G.args.get_arg('series_id')}/{e['id']}/{stream}")
                
                # create mfo file for movie   
                thumbnail = e["images"]["thumbnail"][0]
                thumbnail = max(thumbnail, key=lambda x: x["width"])
                movie = {
                    "movie": {
                        "title": f'{e["season_title"]} {e["title"]}',
                        "plot": e["description"],
                        "thumb": [
                            {
                                "@aspect": "poster",
                                "#text": poster_tall_images["source"]
                            },
                            {
                                "@aspect": "banner",
                                "#text": poster_wide_images["source"]
                            },
                        ],
                        "fanart": {
                            "thumb": {
                                "@aspect": "thumb",
                                "@preview": thumbnail["source"],
                                "#text": thumbnail["source"]
                            }
                        },
                        "fileinfo": {
                            "streamdetails": {
                                "video": {
                                    "durationinseconds": e["duration_ms"] / 1000
                                }
                            }
                        }
                    }
                }
                
                
                with xbmcvfs.File(f"{file_name}.nfo", 'w') as f:
                    f.write(xmltodict.unparse(movie, pretty=True))
            elif item_type == 'episode':
                
                # create folder season
                file_path = f"{file_path_tv_show}/{s['title']}"
                
                if not xbmcvfs.exists(file_path):
                    xbmcvfs.mkdir(file_path)
            
                # create strm file from episode
                file_path = f"{file_path_tv_show}/{s['title']}"
                file_name = f"{file_path}/S{e['season_number']}E{e['episode_number']}"
                panel = e.get('panel') or e
                stream = utils.get_stream_id_from_item(panel)
                
                with xbmcvfs.File(f"{file_name}.strm", 'w') as f:
                    f.write(f"plugin://plugin.video.crunchyroll/video/{G.args.get_arg('series_id')}/{e['id']}/{stream}")
                
                # create mfo file from episode   
                thumbnail = e["images"]["thumbnail"][0]
                thumbnail = max(thumbnail, key=lambda x: x["width"])
                episode = {
                    "episodedetails": {
                        "title": f'{e["season_title"]} {e["title"]}',
                        "plot": e["description"],
                        "thumb": {
                            "@aspect": "thumb",
                            "@preview": thumbnail["source"],
                            "#text": thumbnail["source"]
                        },
                        "season": e["season_number"],
                        "episode": e["episode_number"],
                        "aired": e["episode_air_date"],
                        "fileinfo": {
                            "streamdetails": {
                                "video": {
                                    "durationinseconds": e["duration_ms"] / 1000
                                }
                            }
                        }
                    }
                }
                
                
                with xbmcvfs.File(f"{file_name}.nfo", 'w') as f:
                    f.write(xmltodict.unparse(episode, pretty=True))
            else:
                utils.crunchy_log(
                    "get_listables_from_response | unhandled index for metadata. %s" % (json.dumps(e, indent=4)),
                    xbmc.LOGERROR
                )
                continue
    pDialog.close()
    xbmcgui.Dialog().notification('Addon configurado','Episodes Added to the Library', xbmcgui.NOTIFICATION_INFO)
    xbmc.executebuiltin(f'UpdateLibrary(video)')
    return True