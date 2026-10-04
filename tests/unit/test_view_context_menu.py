"""
Unit tests for the 'episodes' context menu entry built by view.add_listables.

Episode items jump to the wanted season version (episode_target), season items to their own
version. With a known audio locale the target is the season_view_audio route, else season_view.
ctx.args is the shared module-level mock from conftest, so every attribute change goes through monkeypatch.
"""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import resources.lib.view as view
from resources.lib.models.base import ListableItem
from resources.lib.models.content import EpisodeData, SeasonData

ADDONURL = "plugin://plugin.video.crunchyroll"
EPISODES_LABEL = "String_30046"

DUB_SETTINGS = {
    "filter_dubs_by_language": "true",
    "show_dubs_by_language": "true",
    "show_dubs_by_language_fallback": "true",
}
FILTER_OFF_SETTINGS = {"filter_dubs_by_language": "false"}


def _load_fixture(name):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return copy.deepcopy(json.load(f)[name])


def _seasons_v1_item(season_id):
    items = _load_fixture("seasons_V1")["response"]["data"]
    return next(item for item in items if item["id"] == season_id)


@pytest.fixture
def list_item():
    return MagicMock()


@pytest.fixture
def configure(ctx, monkeypatch, list_item):
    async def _no_complement(listables, api, args):
        return {"playheads": {}, "objects": {}, "watchlist": {}}

    monkeypatch.setattr(view, "complement_listables", _no_complement)
    monkeypatch.setattr(view, "xbmcplugin", MagicMock())
    monkeypatch.setattr(ListableItem, "to_item", lambda self, addon=None: list_item)
    monkeypatch.setattr(ctx.args, "addonurl", ADDONURL)
    monkeypatch.setattr(ctx.args, "argv", [ADDONURL, "1", ""])
    monkeypatch.setattr(ctx.args, "subtitle", "de-DE")
    monkeypatch.setattr(ctx.args, "subtitle_fallback", "en-US")

    def _configure(settings):
        monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: settings.get(name, "false"))

    return _configure


def _episodes_action(ctx, list_item, listable):
    view.add_listables(ctx, [listable], is_folder=False, options=view.OPT_CTX_EPISODES)

    list_item.addContextMenuItems.assert_called_once()
    entries = list_item.addContextMenuItems.call_args.args[0]
    actions = [action for label, action in entries if label == EPISODES_LABEL]
    assert len(actions) == 1
    return actions[0]


def test_watchlist_episode_with_dub_settings_targets_de_version(ctx, configure, list_item):
    configure(DUB_SETTINGS)
    episode = EpisodeData(_load_fixture("watchlist_episode_item"))

    action = _episodes_action(ctx, list_item, episode)

    assert action == f"Container.Update({ADDONURL}/series/GR9P57W96/GS00380130DEDE/audio/de-DE)"


def test_watchlist_episode_with_filter_off_targets_own_version(ctx, configure, list_item):
    configure(FILTER_OFF_SETTINGS)
    episode = EpisodeData(_load_fixture("watchlist_episode_item"))

    action = _episodes_action(ctx, list_item, episode)

    assert action == f"Container.Update({ADDONURL}/series/GR9P57W96/GS00380130JAJP/audio/ja-JP)"


def test_season_with_audio_locale_targets_own_version(ctx, configure, list_item):
    configure(DUB_SETTINGS)
    season = SeasonData(_seasons_v1_item("GY19CPGQ9"))

    action = _episodes_action(ctx, list_item, season)

    assert action == f"Container.Update({ADDONURL}/series/GQWH0M1J3/GY19CPGQ9/audio/de-DE)"


def test_season_without_audio_locale_targets_season_view(ctx, configure, list_item):
    configure(DUB_SETTINGS)
    item = _seasons_v1_item("GY19CPGQ9")
    item["audio_locale"] = None
    season = SeasonData(item)

    action = _episodes_action(ctx, list_item, season)

    assert action == f"Container.Update({ADDONURL}/series/GQWH0M1J3/GY19CPGQ9)"


def test_episode_without_audio_and_versions_targets_season_view(ctx, configure, list_item):
    configure(DUB_SETTINGS)
    item = _load_fixture("watchlist_episode_item")
    for key in ("audio_locale", "versions"):
        item["panel"]["episode_metadata"].pop(key)
    episode = EpisodeData(item)

    action = _episodes_action(ctx, list_item, episode)

    assert action == f"Container.Update({ADDONURL}/series/GR9P57W96/GS00380130JAJP)"
