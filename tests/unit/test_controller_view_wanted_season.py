"""
Unit tests for controller.view_wanted_season (decision 7.8).

The 'goto season' context menu of an episode links to the season_view_wanted route with the
episode's own season and audio. At click time the seasons of the series are loaded and the wanted
season version is picked by the season list rules (4.1); its audio counts as explicit, so the
episode filter of view_episodes applies. Errors or no wanted version fall back to the URL values.
ctx.args is the shared module-level mock from conftest, so every attribute change goes through monkeypatch.
"""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import resources.lib.controller as controller
from resources.lib.models.content import EpisodeData

SEASONS_ENDPOINT = "https://www.crunchyroll.com/content/v2/cms/series/{}/seasons"
EPISODES_ENDPOINT = "https://www.crunchyroll.com/content/v2/cms/seasons/{}/episodes"

SERIES_ID = "G24H1N3MP"
OWN_SEASON_ID = "GS00374452ENUS"
OWN_AUDIO = "en-US"
DE_FIXTURE = "episodes_GY19CPGQ9_V3"

DUB_SETTINGS = {
    "filter_dubs_by_language": "true",
    "show_dubs_by_language": "true",
    "show_dubs_by_language_fallback": "true",
}
FILTER_OFF_SETTINGS = {"filter_dubs_by_language": "false"}

# Season item of series G24H1N3MP (Mushoku Tensei) as listed by the seasons response in the Kodi log 2026-10-04.
MUSHOKU_SEASON_ITEM = {
    "id": "GS00374452DEDE",
    "series_id": SERIES_ID,
    "title": "Mushoku Tensei: Jobless Reincarnation",
    "audio_locale": "de-DE",
    "versions": [
        {"audio_locale": "ja-JP", "guid": "GS00374452JAJP", "original": True, "variant": ""},
        {"audio_locale": "en-US", "guid": "GS00374452ENUS", "original": False, "variant": ""},
        {"audio_locale": "es-419", "guid": "GS00374452ES419", "original": False, "variant": ""},
        {"audio_locale": "pt-BR", "guid": "GS00374452PTBR", "original": False, "variant": ""},
        {"audio_locale": "es-ES", "guid": "GS00374452ESES", "original": False, "variant": ""},
        {"audio_locale": "fr-FR", "guid": "GS00374452FRFR", "original": False, "variant": ""},
        {"audio_locale": "it-IT", "guid": "GS00374452ITIT", "original": False, "variant": ""},
        {"audio_locale": "de-DE", "guid": "GS00374452DEDE", "original": False, "variant": ""},
    ],
}


def _load_episodes_response(name=DE_FIXTURE):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return copy.deepcopy(json.load(f)[name]["response"])


def _episodes_in_audio(audio_locale):
    response = _load_episodes_response()
    for item in response["data"]:
        item["audio_locale"] = audio_locale
    return response


def _seasons_response(key="data"):
    return {key: [copy.deepcopy(MUSHOKU_SEASON_ITEM)], "total": 1}


@pytest.fixture
def view_mock(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(controller, "view", mock)
    return mock


@pytest.fixture
def render_error_mock(monkeypatch):
    mock = MagicMock(return_value=False)
    monkeypatch.setattr(controller, "render_error_directory", mock)
    return mock


@pytest.fixture
def log_mock(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(controller, "crunchy_log", mock)
    return mock


@pytest.fixture
def configure(ctx, monkeypatch, view_mock, render_error_mock, log_mock):
    def _configure(settings, responses):
        url_args = {"series_id": SERIES_ID, "season_id": OWN_SEASON_ID, "audio_locale": OWN_AUDIO}

        monkeypatch.setattr(ctx.args, "subtitle", "de-DE")
        monkeypatch.setattr(ctx.args, "subtitle_fallback", "en-US")
        monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: settings.get(name, "false"))
        monkeypatch.setattr(
            ctx.args,
            "get_arg",
            lambda key, default=None, *args, **kwargs: url_args.get(key, default),
        )
        ctx.api.SEASONS_ENDPOINT = SEASONS_ENDPOINT
        ctx.api.EPISODES_ENDPOINT = EPISODES_ENDPOINT
        ctx.api.account_data.default_audio_language = "ja-JP"
        ctx.api.make_request.side_effect = list(responses)

    return _configure


def _call(ctx, index):
    return ctx.api.make_request.call_args_list[index].kwargs


def _listables(view_mock):
    view_mock.add_listables.assert_called_once()
    return view_mock.add_listables.call_args.kwargs["listables"]


def test_seasons_request_carries_only_the_locale(ctx, configure):
    configure(DUB_SETTINGS, [_seasons_response(), _load_episodes_response()])

    controller.view_wanted_season(ctx)

    seasons_call = _call(ctx, 0)
    assert seasons_call["url"] == SEASONS_ENDPOINT.format(SERIES_ID)
    assert seasons_call["params"] == {"locale": "de-DE"}


def test_mushoku_episodes_of_resolved_german_season_are_requested(ctx, configure):
    """Kodi log 2026-10-04: the English season of episode 13 resolves to the German season version."""
    configure(DUB_SETTINGS, [_seasons_response(), _load_episodes_response()])

    controller.view_wanted_season(ctx)

    assert ctx.api.make_request.call_count == 2
    episodes_call = _call(ctx, 1)
    assert episodes_call["url"] == EPISODES_ENDPOINT.format("GS00374452DEDE")
    assert episodes_call["params"] == {"locale": "de-DE", "preferred_audio_language": "de-DE"}


def test_resolved_season_episodes_are_listed(ctx, configure, view_mock):
    response = _load_episodes_response()
    expected_ids = [item["id"] for item in response["data"]]
    configure(DUB_SETTINGS, [_seasons_response(), response])

    result = controller.view_wanted_season(ctx)

    assert result is True
    listables = _listables(view_mock)
    assert all(isinstance(item, EpisodeData) for item in listables)
    assert [item.id for item in listables] == expected_ids


def test_resolved_audio_is_explicit_and_hides_other_audio(ctx, configure, view_mock):
    """Step 3b filter: the resolved audio counts as explicit, so episodes not in de-DE are hidden."""
    response = _load_episodes_response()
    for item in response["data"][-2:]:
        item["audio_locale"] = "ja-JP"
    expected_ids = [item["id"] for item in response["data"][:-2]]
    configure(DUB_SETTINGS, [_seasons_response(), response])

    controller.view_wanted_season(ctx)

    listables = _listables(view_mock)
    assert [item.id for item in listables] == expected_ids
    assert all(item.audio_locale == "de-DE" for item in listables)


def test_items_keyed_seasons_response_is_read(ctx, configure):
    configure(DUB_SETTINGS, [_seasons_response(key="items"), _load_episodes_response()])

    controller.view_wanted_season(ctx)

    episodes_call = _call(ctx, -1)
    assert episodes_call["url"] == EPISODES_ENDPOINT.format("GS00374452DEDE")
    assert episodes_call["params"] == {"locale": "de-DE", "preferred_audio_language": "de-DE"}


@pytest.mark.parametrize("seasons_response", [None, {"error": "boom"}], ids=["none", "error_key"])
def test_seasons_error_falls_back_to_own_season_and_audio(ctx, configure, view_mock, seasons_response):
    response = _episodes_in_audio(OWN_AUDIO)
    expected_ids = [item["id"] for item in response["data"]]
    configure(DUB_SETTINGS, [seasons_response, response])

    result = controller.view_wanted_season(ctx)

    assert result is True
    episodes_call = _call(ctx, -1)
    assert episodes_call["url"] == EPISODES_ENDPOINT.format(OWN_SEASON_ID)
    assert episodes_call["params"] == {"locale": "de-DE", "preferred_audio_language": OWN_AUDIO}
    assert [item.id for item in _listables(view_mock)] == expected_ids


def test_no_wanted_version_falls_back_to_own_season_and_audio(ctx, configure, view_mock):
    """Filter off: the resolver returns None, so the episode's own season and audio are used."""
    response = _episodes_in_audio(OWN_AUDIO)
    expected_ids = [item["id"] for item in response["data"]]
    configure(FILTER_OFF_SETTINGS, [_seasons_response(), response])

    result = controller.view_wanted_season(ctx)

    assert result is True
    episodes_call = _call(ctx, -1)
    assert episodes_call["url"] == EPISODES_ENDPOINT.format(OWN_SEASON_ID)
    assert episodes_call["params"] == {"locale": "de-DE", "preferred_audio_language": OWN_AUDIO}
    assert [item.id for item in _listables(view_mock)] == expected_ids


def test_unknown_season_falls_back_to_own_season_and_audio(ctx, configure):
    seasons = _seasons_response()
    seasons["data"][0]["id"] = "GS_OTHER"
    for version in seasons["data"][0]["versions"]:
        version["guid"] = f"GS_OTHER_{version['audio_locale']}"
    configure(DUB_SETTINGS, [seasons, _episodes_in_audio(OWN_AUDIO)])

    controller.view_wanted_season(ctx)

    episodes_call = _call(ctx, -1)
    assert episodes_call["url"] == EPISODES_ENDPOINT.format(OWN_SEASON_ID)
    assert episodes_call["params"] == {"locale": "de-DE", "preferred_audio_language": OWN_AUDIO}
