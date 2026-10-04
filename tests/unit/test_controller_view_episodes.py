"""
Unit tests for controller.view_episodes.

The audio locale comes from the season_view_audio route; old season_view URLs derive it from
the language settings. The account default audio language is never used. ctx.args is the shared
module-level mock from conftest, so every attribute change goes through monkeypatch.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import resources.lib.controller as controller
from resources.lib.models.content import EpisodeData

SERIES_ID = "GQWH0M1J3"
JA_FIXTURE = "episodes_GYE5CQNJ2_V2"
DE_FIXTURE = "episodes_GY19CPGQ9_V3"

DUB_SETTINGS = {
    "filter_dubs_by_language": "true",
    "show_dubs_by_language": "true",
    "show_dubs_by_language_fallback": "true",
}
SUBS_ONLY_SETTINGS = {
    "filter_dubs_by_language": "true",
    "show_subs_by_language": "true",
}
FILTER_OFF_SETTINGS = {"filter_dubs_by_language": "false"}


def _load_episodes_response(name):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return json.load(f)[name]["response"]


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
    def _configure(settings, audio_locale=None, fixture=DE_FIXTURE, season_id="GY19CPGQ9"):
        url_args = {"series_id": SERIES_ID, "season_id": season_id}
        if audio_locale is not None:
            url_args["audio_locale"] = audio_locale

        monkeypatch.setattr(ctx.args, "subtitle", "de-DE")
        monkeypatch.setattr(ctx.args, "subtitle_fallback", "en-US")
        monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: settings.get(name, "false"))
        monkeypatch.setattr(
            ctx.args,
            "get_arg",
            lambda key, default=None, *args, **kwargs: url_args.get(key, default),
        )
        ctx.api.account_data.default_audio_language = "ja-JP"
        ctx.api.make_request.return_value = _load_episodes_response(fixture)

    return _configure


def _request_params(ctx):
    ctx.api.make_request.assert_called_once()
    return ctx.api.make_request.call_args.kwargs["params"]


def _warning_calls(log_mock):
    warning = controller.xbmc.LOGWARNING
    return [
        c
        for c in log_mock.call_args_list
        if (len(c.args) > 1 and c.args[1] is warning) or c.kwargs.get("loglevel") is warning
    ]


@pytest.mark.parametrize(
    "settings",
    [DUB_SETTINGS, SUBS_ONLY_SETTINGS, FILTER_OFF_SETTINGS],
    ids=["dubs", "subs_only", "filter_off"],
)
def test_url_audio_locale_is_sent_as_preferred_audio(ctx, configure, settings):
    configure(settings, audio_locale="de-DE")

    controller.view_episodes(ctx)

    assert _request_params(ctx) == {"locale": "de-DE", "preferred_audio_language": "de-DE"}


def test_without_url_audio_dub_settings_prefer_primary_dub(ctx, configure):
    configure(DUB_SETTINGS)

    controller.view_episodes(ctx)

    assert _request_params(ctx) == {"locale": "de-DE", "preferred_audio_language": "de-DE"}


def test_without_url_audio_subs_only_sends_no_preferred_audio(ctx, configure):
    configure(SUBS_ONLY_SETTINGS, fixture=JA_FIXTURE, season_id="GYE5CQNJ2")

    controller.view_episodes(ctx)

    assert _request_params(ctx) == {"locale": "de-DE"}


def test_without_url_audio_filter_off_sends_no_preferred_audio(ctx, configure):
    configure(FILTER_OFF_SETTINGS, fixture=JA_FIXTURE, season_id="GYE5CQNJ2")

    controller.view_episodes(ctx)

    assert _request_params(ctx) == {"locale": "de-DE"}


@pytest.mark.parametrize(
    "settings, audio_locale",
    [
        (DUB_SETTINGS, "de-DE"),
        (DUB_SETTINGS, None),
        (SUBS_ONLY_SETTINGS, None),
        (FILTER_OFF_SETTINGS, None),
    ],
    ids=["dubs_url", "dubs_no_url", "subs_only_no_url", "filter_off_no_url"],
)
def test_never_force_locale_nor_account_language(ctx, configure, settings, audio_locale):
    configure(settings, audio_locale=audio_locale)

    controller.view_episodes(ctx)

    params = _request_params(ctx)
    assert "force_locale" not in params
    assert params.get("preferred_audio_language") != "ja-JP"


def test_each_episode_listed_once_with_item_id(ctx, configure, view_mock):
    configure(DUB_SETTINGS, audio_locale="de-DE")
    expected_ids = [item["id"] for item in _load_episodes_response(DE_FIXTURE)["data"]]

    result = controller.view_episodes(ctx)

    assert result is True
    view_mock.add_listables.assert_called_once()
    listables = view_mock.add_listables.call_args.kwargs["listables"]
    assert len(listables) == 24
    assert all(isinstance(item, EpisodeData) for item in listables)
    assert [item.id for item in listables] == expected_ids
    assert len(set(item.id for item in listables)) == 24


def test_warning_when_response_audio_differs_from_url_audio(ctx, configure, log_mock):
    configure(DUB_SETTINGS, audio_locale="de-DE", fixture=JA_FIXTURE)

    controller.view_episodes(ctx)

    warnings = _warning_calls(log_mock)
    assert len(warnings) == 1
    assert "24" in str(warnings[0].args[0])


def test_no_warning_when_response_audio_matches(ctx, configure, log_mock):
    configure(DUB_SETTINGS, audio_locale="de-DE", fixture=DE_FIXTURE)

    controller.view_episodes(ctx)

    assert _warning_calls(log_mock) == []


def test_no_warning_without_requested_audio(ctx, configure, log_mock):
    """Inferred: without a requested audio locale there is nothing to deviate from"""
    configure(SUBS_ONLY_SETTINGS, fixture=DE_FIXTURE)

    controller.view_episodes(ctx)

    assert _warning_calls(log_mock) == []
