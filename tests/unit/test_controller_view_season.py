"""
Unit tests for controller.view_season.

The seasons request carries only the locale; version selection happens locally via
select_season_versions. ctx.args is the shared module-level mock from conftest, so every
attribute change goes through monkeypatch to be undone after each test.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import resources.lib.controller as controller
from resources.lib.models.content import SeasonData

SERIES_ID = "GQWH0M1J3"


def _load_seasons_response():
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        return json.load(f)["seasons_V1"]["response"]


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
def configure(ctx, monkeypatch):
    def _configure(settings, subtitle="de-DE", subtitle_fallback="en-US"):
        monkeypatch.setattr(ctx.args, "subtitle", subtitle)
        monkeypatch.setattr(ctx.args, "subtitle_fallback", subtitle_fallback)
        monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: settings.get(name, "false"))
        monkeypatch.setattr(
            ctx.args,
            "get_arg",
            lambda key, default=None, *args, **kwargs: SERIES_ID if key == "series_id" else default,
        )
        ctx.api.make_request.return_value = _load_seasons_response()

    return _configure


DUB_SETTINGS = {
    "filter_dubs_by_language": "true",
    "show_dubs_by_language": "true",
    "show_dubs_by_language_fallback": "true",
}


def _listed_ids(view_mock):
    view_mock.add_listables.assert_called_once()
    listables = view_mock.add_listables.call_args.kwargs["listables"]
    assert all(isinstance(item, SeasonData) for item in listables)
    return [item.id for item in listables]


@pytest.mark.parametrize(
    "settings",
    [{"filter_dubs_by_language": "false"}, DUB_SETTINGS],
    ids=["filter_off", "filter_on"],
)
def test_request_params_contain_only_locale(ctx, configure, view_mock, render_error_mock, settings):
    configure(settings)

    controller.view_season(ctx)

    ctx.api.make_request.assert_called_once()
    assert ctx.api.make_request.call_args.kwargs["params"] == {"locale": "de-DE"}


def test_dub_settings_list_primary_and_fallback_dub(ctx, configure, view_mock, render_error_mock):
    configure(DUB_SETTINGS)

    result = controller.view_season(ctx)

    assert result is True
    assert _listed_ids(view_mock) == ["GY19CPGQ9", "GRJQC1EN0"]
    render_error_mock.assert_not_called()


def test_filter_off_lists_all_versions(ctx, configure, view_mock, render_error_mock):
    configure({"filter_dubs_by_language": "false"})

    controller.view_season(ctx)

    assert _listed_ids(view_mock) == [
        "GYE5CQNJ2",
        "GY19CPGQ9",
        "GRJQC1EN0",
        "GR9PC2GZ8",
        "GR49C78K8",
        "G6X0C4Z10",
        "GR75CDJPE",
    ]


def test_no_wanted_version_renders_hint(ctx, configure, view_mock, render_error_mock):
    configure(
        {"filter_dubs_by_language": "true", "show_dubs_by_language": "true"},
        subtitle="it-IT",
        subtitle_fallback=None,
    )

    result = controller.view_season(ctx)

    render_error_mock.assert_called_once_with(ctx, title_id=30091)
    view_mock.add_listables.assert_not_called()
    assert result is False
