"""
Unit tests for controller.view_episodes.

The audio locale comes from the season_view_audio route; old season_view URLs derive it from
the language settings. The account default audio language is never used. ctx.args is the shared
module-level mock from conftest, so every attribute change goes through monkeypatch.
"""

import copy
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


def _log_level(call):
    if len(call.args) > 1:
        return call.args[1]
    return call.kwargs.get("loglevel", controller.xbmc.LOGINFO)


def _calls_at_level(log_mock, level):
    return [c for c in log_mock.call_args_list if _log_level(c) is level]


def _warning_calls(log_mock):
    return _calls_at_level(log_mock, controller.xbmc.LOGWARNING)


def _info_calls(log_mock):
    return _calls_at_level(log_mock, controller.xbmc.LOGINFO)


def _de_response_with_backlog(backlog_count=2, backlog_audio="ja-JP"):
    """DE fixture whose last items carry another audio, like the API fills a dub backlog"""
    response = copy.deepcopy(_load_episodes_response(DE_FIXTURE))
    for item in response["data"][-backlog_count:]:
        if backlog_audio is None:
            item.pop("audio_locale", None)
        else:
            item["audio_locale"] = backlog_audio
    return response


def _listables(view_mock):
    view_mock.add_listables.assert_called_once()
    return view_mock.add_listables.call_args.kwargs["listables"]


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


@pytest.mark.parametrize(
    "settings, audio_locale",
    [
        (DUB_SETTINGS, "de-DE"),
        (FILTER_OFF_SETTINGS, "de-DE"),
    ],
    ids=["dubs_url", "filter_off_url"],
)
def test_episodes_not_in_requested_audio_are_hidden(ctx, configure, view_mock, settings, audio_locale):
    """Decision 7.7 (user): the API fills a dub backlog with the original version; hide those episodes.

    Only an audio locale from the URL filters; a derived one does not (decision Option 2).
    """
    configure(settings, audio_locale=audio_locale)
    response = _de_response_with_backlog()
    ctx.api.make_request.return_value = response
    expected_ids = [item["id"] for item in response["data"][:-2]]

    result = controller.view_episodes(ctx)

    assert result is True
    listables = _listables(view_mock)
    assert all(isinstance(item, EpisodeData) for item in listables)
    assert [item.id for item in listables] == expected_ids
    assert all(item.audio_locale == "de-DE" for item in listables)


def test_derived_audio_is_sent_but_does_not_hide_backlog(ctx, configure, view_mock, log_mock):
    """Decision Option 2: audio derived from settings (old URL) is preferred, but the list stays unfiltered"""
    configure(DUB_SETTINGS)
    response = _de_response_with_backlog()
    ctx.api.make_request.return_value = response
    expected_ids = [item["id"] for item in response["data"]]

    result = controller.view_episodes(ctx)

    assert result is True
    assert _request_params(ctx)["preferred_audio_language"] == "de-DE"
    listables = _listables(view_mock)
    assert len(listables) == 24
    assert [item.id for item in listables] == expected_ids
    assert _warning_calls(log_mock) == []
    assert _info_calls(log_mock) == []


def test_derived_audio_without_match_renders_no_hint(ctx, configure, view_mock, render_error_mock):
    """Decision Option 2: with derived audio nothing is hidden, so no hint 30091 even if nothing matches"""
    configure(DUB_SETTINGS, fixture=JA_FIXTURE, season_id="GYE5CQNJ2")
    expected_ids = [item["id"] for item in _load_episodes_response(JA_FIXTURE)["data"]]

    result = controller.view_episodes(ctx)

    assert result is True
    render_error_mock.assert_not_called()
    assert [item.id for item in _listables(view_mock)] == expected_ids
    assert len(expected_ids) == 24


def test_episodes_without_audio_locale_are_hidden_when_audio_requested(ctx, configure, view_mock):
    """Decision 7.7: an episode of unknown audio is not the requested dub"""
    configure(DUB_SETTINGS, audio_locale="de-DE")
    response = _de_response_with_backlog(backlog_audio=None)
    ctx.api.make_request.return_value = response
    expected_ids = [item["id"] for item in response["data"][:-2]]

    controller.view_episodes(ctx)

    assert [item.id for item in _listables(view_mock)] == expected_ids


def test_mixed_response_passes_unchanged_without_requested_audio(ctx, configure, view_mock):
    """Decision 7.7: without a requested audio locale there is nothing to filter by"""
    configure(SUBS_ONLY_SETTINGS)
    response = _de_response_with_backlog()
    ctx.api.make_request.return_value = response
    expected_ids = [item["id"] for item in response["data"]]

    controller.view_episodes(ctx)

    assert [item.id for item in _listables(view_mock)] == expected_ids


def test_all_episodes_hidden_renders_no_matching_version_hint(ctx, configure, view_mock, render_error_mock):
    """Decision 7.7 with decision 7.2: nothing left after hiding shows hint 30091"""
    configure(DUB_SETTINGS, audio_locale="de-DE", fixture=JA_FIXTURE, season_id="GYE5CQNJ2")

    result = controller.view_episodes(ctx)

    render_error_mock.assert_called_once_with(ctx, title_id=30091)
    view_mock.add_listables.assert_not_called()
    assert result is render_error_mock.return_value


def test_hidden_episodes_are_logged_as_info_not_warning(ctx, configure, log_mock):
    """Decision 7.7: hiding the dub backlog is expected behaviour, so info log instead of the old warning"""
    configure(DUB_SETTINGS, audio_locale="de-DE")
    ctx.api.make_request.return_value = _de_response_with_backlog()

    controller.view_episodes(ctx)

    assert _warning_calls(log_mock) == []
    infos = _info_calls(log_mock)
    assert len(infos) == 1
    message = str(infos[0].args[0])
    assert "2" in message
    assert "24" in message
    assert "de-DE" in message


@pytest.mark.parametrize(
    "settings, audio_locale",
    [(DUB_SETTINGS, "de-DE"), (SUBS_ONLY_SETTINGS, None)],
    ids=["audio_matches", "no_requested_audio"],
)
def test_no_log_when_nothing_hidden(ctx, configure, log_mock, settings, audio_locale):
    """Decision 7.7: the info line appears only when episodes were hidden; no warning at all"""
    configure(settings, audio_locale=audio_locale)
    if audio_locale is None:
        ctx.api.make_request.return_value = _de_response_with_backlog()

    controller.view_episodes(ctx)

    assert _warning_calls(log_mock) == []
    assert _info_calls(log_mock) == []
