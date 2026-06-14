"""
Focused unit tests for the refactored resources.lib.utils package.

Covers filters, formatting, images, and small api_data helpers.
Tests import from the submodules to prove the split works.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

import resources.lib.utils.api_data as api_data
import resources.lib.utils.filters as filters
import resources.lib.utils.formatting as formatting
import resources.lib.utils.images as images
from resources.lib.models.exceptions import CrunchyrollError


@pytest.fixture
def mock_utils_args():
    addon = MagicMock()
    args = MagicMock()
    args.addon = addon
    args.subtitle = "de-DE"
    args.subtitle_fallback = "en-US"
    args.addon_name = "CrunchyrollTest"
    return args


@pytest.fixture
def mock_utils_api():
    api = MagicMock()
    api.STATIC_IMG_PROFILE = "https://static/img/"
    api.STATIC_WALLPAPER_PROFILE = "https://static/wallpaper/"
    return api


class TestFilters:
    def test_filter_series_disabled_returns_true(self, mock_utils_args):
        mock_utils_args.addon.getSetting.return_value = "false"
        result = filters.filter_series(
            {"panel": {"series_metadata": {"audio_locales": ["ja-JP"]}}},
            args=mock_utils_args,
        )
        assert result is True

    def test_filter_series_main_audio_matches(self, mock_utils_args):
        def setting(name):
            return {"filter_dubs_by_language": "true", "show_dubs_by_language": "true"}.get(name, "false")

        mock_utils_args.addon.getSetting.side_effect = setting
        result = filters.filter_series(
            {"panel": {"series_metadata": {"audio_locales": ["de-DE"]}}},
            args=mock_utils_args,
        )
        assert result is True

    def test_filter_series_fallback_audio_matches(self, mock_utils_args):
        def setting(name):
            return {
                "filter_dubs_by_language": "true",
                "show_dubs_by_language_fallback": "true",
            }.get(name, "false")

        mock_utils_args.addon.getSetting.side_effect = setting
        result = filters.filter_series(
            {"panel": {"series_metadata": {"audio_locales": ["en-US"]}}},
            args=mock_utils_args,
        )
        assert result is True

    def test_filter_series_japanese_with_subtitles(self, mock_utils_args):
        def setting(name):
            return {
                "filter_dubs_by_language": "true",
                "show_subs_by_language": "true",
            }.get(name, "false")

        mock_utils_args.addon.getSetting.side_effect = setting
        assert filters.filter_series(
            {
                "panel": {
                    "series_metadata": {
                        "audio_locales": ["ja-JP"],
                        "subtitle_locales": ["de-DE"],
                    }
                }
            },
            args=mock_utils_args,
        ) is True

    def test_filter_series_no_match(self, mock_utils_args):
        def setting(name):
            return {"filter_dubs_by_language": "true", "show_dubs_by_language": "true"}.get(name, "false")

        mock_utils_args.addon.getSetting.side_effect = setting
        mock_utils_args.subtitle = "fr-FR"
        result = filters.filter_series(
            {"panel": {"series_metadata": {"audio_locales": ["de-DE"]}}},
            args=mock_utils_args,
        )
        assert result is False

    def test_filter_seasons_main_audio_matches(self, mock_utils_args):
        def setting(name):
            return {"filter_dubs_by_language": "true", "show_dubs_by_language": "true"}.get(name, "false")

        mock_utils_args.addon.getSetting.side_effect = setting
        assert filters.filter_seasons({"audio_locale": "de-DE"}, args=mock_utils_args) is True

    def test_filter_seasons_japanese_with_fallback_subs(self, mock_utils_args):
        def setting(name):
            return {
                "filter_dubs_by_language": "true",
                "show_subs_by_language": "true",
            }.get(name, "false")

        mock_utils_args.addon.getSetting.side_effect = setting
        result = filters.filter_seasons(
            {"audio_locale": "ja-JP", "subtitle_locales": ["en-US"]},
            args=mock_utils_args,
        )
        assert result is True


class TestFormatting:
    def test_two_digits_zero(self):
        assert formatting.two_digits(0) == "00"

    def test_two_digits_single(self):
        assert formatting.two_digits(5) == "05"

    def test_two_digits_double(self):
        assert formatting.two_digits(12) == "12"

    def test_format_long_episode_title(self):
        assert formatting.format_long_episode_title("Sword Art", 1, 5, "Title") == "Sword Art - S01E05 - Title"

    def test_format_short_episode_title(self):
        assert formatting.format_short_episode_title(7, "Short") == "07 - Short"

    def test_convert_text_to_date(self):
        assert formatting.convert_text_to_date("2024-03-15") == datetime(2024, 3, 15)

    def test_sort_episodes_unwatched_first(self):
        class FakeEp:
            pass

        ep1 = FakeEp()
        ep1.id = "e1"
        ep1.playcount = 0
        ep1.aired = "2024-01-01"

        ep2 = FakeEp()
        ep2.id = "e2"
        ep2.playcount = 1
        ep2.aired = "2024-01-02"

        ep3 = FakeEp()
        ep3.id = "e3"
        ep3.playcount = 0
        ep3.aired = "2024-01-03"

        # sort_episodes checks for EpisodeData/MovieData; patch the check
        with patch.object(formatting, "EpisodeData", FakeEp), patch.object(formatting, "MovieData", FakeEp):
            sorted_items = formatting.sort_episodes([ep1, ep2, ep3])

        assert [item.id for item in sorted_items] == ["e3", "e1", "e2"]

    def test_sort_episodes_movies_are_accepted(self):
        class FakeEp:
            pass

        class FakeMovie:
            pass

        movie = FakeMovie()
        movie.id = "m1"
        movie.playcount = 0
        movie.aired = "2024-02-01"

        ep = FakeEp()
        ep.id = "e1"
        ep.playcount = 0
        ep.aired = "2024-01-01"

        with patch.object(formatting, "EpisodeData", FakeEp), patch.object(formatting, "MovieData", FakeMovie):
            sorted_items = formatting.sort_episodes([movie, ep])

        assert {item.id for item in sorted_items} == {"m1", "e1"}


class TestImages:
    def test_get_img_from_static_normal(self, mock_utils_api):
        assert images.get_img_from_static("poster.jpg", api=mock_utils_api) == "https://static/img/poster.jpg"

    def test_get_img_from_static_wallpaper(self, mock_utils_api):
        assert images.get_img_from_static("bg.jpg", image_type="wallpaper", api=mock_utils_api) == "https://static/wallpaper/bg.jpg"

    def test_get_img_from_static_none(self):
        assert images.get_img_from_static(None, api=MagicMock()) is None

    def test_get_img_from_struct_extracts_source(self):
        item = {"images": {"poster_tall": [{"source": "https://img/1"}]}}
        assert images.get_img_from_struct(item, "poster_tall", depth=1) == "https://img/1"

    def test_get_img_from_struct_missing(self):
        assert images.get_img_from_struct({}, "poster_tall") is None

    def test_infer_img_from_id_backdrop(self):
        assert images.infer_img_from_id("GQWH0M1J3", "backdrop_wide").startswith("https://imgsrv.crunchyroll.com/")

    def test_infer_img_from_id_title_logo(self):
        assert images.infer_img_from_id("GQWH0M1J3", "title_logo").endswith("/keyart/GQWH0M1J3-title_logo-en-us")

    def test_infer_img_from_id_invalid_type(self):
        assert images.infer_img_from_id("GQWH0M1J3", "unknown") is None


class TestApiDataHelpers:
    def test_get_stream_id_from_item(self):
        item = {"__links__": {"streams": {"href": "https://crunchyroll.com/videos/GX9UQKJW2/streams"}}}
        assert api_data.get_stream_id_from_item(item) == "GX9UQKJW2"

    def test_get_stream_id_from_streams_link(self):
        item = {"streams_link": "https://crunchyroll.com/videos/GX9UQKJW2/streams"}
        assert api_data.get_stream_id_from_item(item) == "GX9UQKJW2"

    def test_get_stream_id_missing_raises(self):
        with pytest.raises(CrunchyrollError):
            api_data.get_stream_id_from_item({})

    def test_get_listables_from_response_detects_series(self):
        args = MagicMock()
        args.addon.getSetting.return_value = "false"
        data = [{"type": "series", "panel": {"series_metadata": {"audio_locales": ["de-DE"]}}}]
        result = api_data.get_listables_from_response(data, args=args)
        assert len(result) == 1
        assert isinstance(result[0], type(result[0]))  # just ensure it is a model instance

    def test_get_listables_from_response_type_hint(self):
        args = MagicMock()
        args.addon.getSetting.return_value = "false"
        # Build a minimal valid episode struct; use a MagicMock to avoid
        # constructing the full EpisodeData object graph.
        ep = MagicMock()
        with patch("resources.lib.utils.api_data.EpisodeData", return_value=ep) as mock_factory:
            data = [{"episode_number": 1}]
            result = api_data.get_listables_from_response(data, item_type_hint="episode", args=args)
            assert len(result) == 1
            assert result[0] is ep
            mock_factory.assert_called_once_with(data[0])
