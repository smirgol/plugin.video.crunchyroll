"""
Unit tests for resources.lib.presentation.

The presentation layer is intentionally free of the G singleton, so these
exercise pure functions.
"""

from unittest.mock import patch

import pytest

from resources.lib import presentation


class FakeListable:
    title = "Item"
    thumb = None
    poster = None
    fanart = None
    landscape = None
    clearart = None
    clearlogo = None

    def get_info(self):
        return {"title": "Item", "plot": "Plot", "episode": 1}


class FakePlayable(FakeListable):
    duration = 1200
    playcount = 0
    playhead = 600


class TestBuildUrl:
    def test_build_url_without_route(self):
        with patch.object(presentation.router, "build_path", return_value="/series/abc"):
            assert presentation.build_url({"series_id": "abc"}, "plugin://foo/") == "plugin://foo/series/abc"

    def test_build_url_with_route(self):
        with patch.object(presentation.router, "create_path_from_route", return_value="/season/abc/123"):
            assert (
                presentation.build_url({"series_id": "abc"}, "plugin://foo/", "season_view")
                == "plugin://foo/season/abc/123"
            )

    def test_build_url_fallback_path(self):
        with patch.object(presentation.router, "build_path", return_value=None):
            assert presentation.build_url({"mode": "main"}, "plugin://foo/") == "plugin://foo/"

    def test_quote_value_int(self):
        assert presentation.quote_value(42) == "42"

    def test_quote_value_str(self):
        assert " " not in presentation.quote_value("hello world")


class TestMakeInfoLabel:
    def test_filters_to_kodi_types(self):
        info = {"title": "T", "plot": "P", "unknown_key": "X", "duration": 120}
        result = presentation.make_info_label(info, {})
        assert result == {"title": "T", "plot": "P", "duration": 120}

    def test_current_args_fill_without_overwrite(self):
        info = {"title": "New"}
        current = {"year": 2024, "title": "Old"}
        result = presentation.make_info_label(info, current)
        assert result["title"] == "New"
        assert result["year"] == 2024

    def test_sync_playcount_from_info(self):
        info = {"title": "T", "playcount": 1}
        result = presentation.make_info_label(info, {}, sync_playtime=True)
        assert result["playcount"] == 1

    def test_sync_playcount_from_args(self):
        result = presentation.make_info_label({}, {"playcount": 0}, sync_playtime=True)
        assert result["playcount"] == 0

    def test_no_sync_playcount_by_default(self):
        info = {"title": "T", "playcount": 1}
        result = presentation.make_info_label(info, {})
        assert "playcount" not in result


class TestPresentListable:
    def test_sets_label_and_info(self):
        listable = FakeListable()
        li = presentation.present_listable(listable)
        li.setLabel.assert_called_once_with("Item")
        li.setInfo.assert_called_once()
        args, kwargs = li.setInfo.call_args
        assert args[0] == "video"
        assert args[1]["title"] == "Item"

    def test_playable_sets_properties(self):
        listable = FakePlayable()
        li = presentation.present_listable(listable)
        li.setProperty.assert_any_call("IsPlayable", "true")
        li.setProperty.assert_any_call("TotalTime", "1200.0")

    def test_sync_playtime_applies_playcount(self):
        listable = FakePlayable()
        li = presentation.present_listable(listable, sync_playtime=True)
        args, kwargs = li.setInfo.call_args
        assert args[1]["playcount"] == 0

    def test_sets_artworks(self):
        listable = FakeListable()
        listable.thumb = "https://thumb"
        listable.poster = "https://poster"
        listable.fanart = "https://fanart"
        li = presentation.present_listable(listable)
        args, kwargs = li.setArt.call_args
        assert args[0]["thumb"] == "https://thumb"
        assert args[0]["poster"] == "https://poster"
        assert args[0]["fanart"] == "https://fanart"

    def test_no_artworks_for_empty_attrs(self):
        listable = FakeListable()
        li = presentation.present_listable(listable)
        args, kwargs = li.setArt.call_args
        assert args[0] == {}


@pytest.mark.parametrize("value,expected", [
    (42, "42"),
    ("hello world", "hello+world"),
])
def test_quote_value(value, expected):
    if isinstance(value, str):
        # space must be quoted
        assert presentation.quote_value(value) == expected
    else:
        assert presentation.quote_value(value) == expected
