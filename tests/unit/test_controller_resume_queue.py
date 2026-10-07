"""
Unit tests for the version switch of top-level entries in controller.show_resume_episodes and show_queue.

Resume and queue entries play the wanted version picked from the episode's versions (Schritt 3d, Issue #136);
the history shows what was actually watched and never switches. ctx.args is the shared module-level mock
from conftest, so every attribute change goes through monkeypatch.
"""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import resources.lib.controller as controller
from resources.lib.models.content import EpisodeData

DUB_SETTINGS = {
    "filter_dubs_by_language": "true",
    "show_dubs_by_language": "true",
    "show_dubs_by_language_fallback": "true",
}
SUBS_AND_DUBS_SETTINGS = {
    "filter_dubs_by_language": "true",
    "show_dubs_by_language": "true",
    "show_subs_by_language": "true",
}
FILTER_OFF_SETTINGS = {"filter_dubs_by_language": "false"}

PLAYHEAD = 321

OWN = {
    "id": "GE00380136JAJP",
    "episode_id": "GE00380136JAJP",
    "stream_id": "GE00380136JAJPV",
    "audio_locale": "ja-JP",
    "season_id": "GS00380130JAJP",
}
GERMAN = {
    "id": "GE00380136DEDE",
    "episode_id": "GE00380136DEDE",
    "stream_id": "GE00380136DEDEV",
    "audio_locale": "de-DE",
    "season_id": "GS00380130DEDE",
}


def _watchlist_episode_item():
    """Watchlist item of Saga of Tanya the Evil in ja-JP, carrying a de-DE version."""
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        item = copy.deepcopy(json.load(f)["watchlist_episode_item"])
    item["playhead"] = PLAYHEAD
    return item


def _response(key):
    return {key: [_watchlist_episode_item()], "total": 1}


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
def configure(ctx, monkeypatch, view_mock, render_error_mock):
    def _configure(settings, response):
        monkeypatch.setattr(ctx.args, "subtitle", "de-DE")
        monkeypatch.setattr(ctx.args, "subtitle_fallback", "en-US")
        monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: settings.get(name, "false"))
        monkeypatch.setattr(ctx.args, "get_arg", lambda key, default=None, *args, **kwargs: default)
        ctx.api.make_request.return_value = response

    return _configure


def _episode(view_mock):
    view_mock.add_listables.assert_called_once()
    listables = view_mock.add_listables.call_args.kwargs["listables"]
    assert len(listables) == 1
    assert isinstance(listables[0], EpisodeData)
    return listables[0]


def _identity(episode):
    """The ids playback and the context menu use; episode_id/stream_id/season_id as get_info() hands them on."""
    info = episode.get_info()
    return {
        "id": episode.id,
        "episode_id": info["episode_id"],
        "stream_id": info["stream_id"],
        "audio_locale": episode.audio_locale,
        "season_id": info["season_id"],
    }


SWITCHING_VIEWS = [
    pytest.param(controller.show_resume_episodes, "data", id="resume"),
    pytest.param(controller.show_queue, "items", id="queue"),
]


@pytest.mark.parametrize(("show", "key"), SWITCHING_VIEWS)
def test_dub_settings_switch_entry_to_wanted_version(ctx, configure, view_mock, render_error_mock, show, key):
    configure(DUB_SETTINGS, _response(key))

    result = show(ctx)

    assert result is True
    render_error_mock.assert_not_called()
    assert _identity(_episode(view_mock)) == GERMAN


@pytest.mark.parametrize(("show", "key"), SWITCHING_VIEWS)
def test_switched_entry_keeps_title_and_series_but_drops_playhead(ctx, configure, view_mock, show, key):
    """Deliberate change (review 2026-10-05): the listed progress belongs to the old id and must not be shown for
    the new id; playhead 0 lets view.complement_listables fetch the progress of the new id."""
    configure(DUB_SETTINGS, _response(key))
    expected = EpisodeData(_watchlist_episode_item())

    show(ctx)

    episode = _episode(view_mock)
    assert episode.title == expected.title
    assert episode.playhead == 0
    assert episode.playcount == 0
    assert episode.duration == expected.duration
    assert episode.series_id == expected.series_id


@pytest.mark.parametrize(("show", "key"), SWITCHING_VIEWS)
@pytest.mark.parametrize("settings", [FILTER_OFF_SETTINGS, SUBS_AND_DUBS_SETTINGS], ids=["filter_off", "subs_dubs"])
def test_entry_keeps_own_version(ctx, configure, view_mock, show, key, settings):
    """Filter off: no switch. Subs and dubs: the own ja-JP original is allowed and stays (Issue #136)."""
    configure(settings, _response(key))

    show(ctx)

    episode = _episode(view_mock)
    assert _identity(episode) == OWN
    assert episode.playhead == PLAYHEAD


def test_history_does_not_switch(ctx, configure, view_mock):
    """The history shows what was actually watched (decision 7.9)."""
    configure(DUB_SETTINGS, _response("data"))

    result = controller.show_history(ctx)

    assert result is True
    episode = _episode(view_mock)
    assert _identity(episode) == OWN
    assert episode.playhead == PLAYHEAD
