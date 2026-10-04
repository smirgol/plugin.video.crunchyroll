"""
Unit tests for resources.lib.router.

The season_view_audio route carries the audio locale of the chosen season version
from the seasons list (or an episode context menu) to view_episodes.
"""

import copy
import json
from pathlib import Path

from resources.lib import router
from resources.lib.models.content import SeasonData

SERIES_ID = "GQWH0M1J3"
DE_ID = "GY19CPGQ9"


def _seasons_v1_item(season_id):
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "version_responses.json") as f:
        items = json.load(f)["seasons_V1"]["response"]["data"]
    return copy.deepcopy(next(item for item in items if item["id"] == season_id))


class TestExtractUrlParams:
    def test_season_view_audio_route_resolves(self):
        params = router.extract_url_params("/series/S1/GY19CPGQ9/audio/de-DE")

        assert params == {
            "series_id": "S1",
            "season_id": "GY19CPGQ9",
            "audio_locale": "de-DE",
            "mode": "episodes",
            "current_route": "season_view_audio",
        }

    def test_season_view_audio_route_with_non_alphabetic_region(self):
        params = router.extract_url_params("/series/S1/GR9PC2GZ8/audio/es-419")

        assert params["current_route"] == "season_view_audio"
        assert params["audio_locale"] == "es-419"

    def test_old_season_view_url_still_resolves(self):
        params = router.extract_url_params("/series/S1/GY19CPGQ9")

        assert params == {
            "series_id": "S1",
            "season_id": "GY19CPGQ9",
            "mode": "episodes",
            "current_route": "season_view",
        }

    def test_offset_route_unaffected(self):
        params = router.extract_url_params("/series/S1/GY19CPGQ9/offset/2")

        assert params == {
            "series_id": "S1",
            "season_id": "GY19CPGQ9",
            "offset": "2",
            "mode": "episodes",
            "current_route": "season_view_with_offset",
        }


class TestBuildPathFromSeasonData:
    def test_season_with_audio_locale_builds_audio_route(self):
        season = SeasonData(_seasons_v1_item(DE_ID))

        assert season.audio_locale == "de-DE"
        assert router.build_path(season.get_info()) == f"/series/{SERIES_ID}/{DE_ID}/audio/de-DE"

    def test_season_without_audio_locale_builds_season_view(self):
        item = _seasons_v1_item(DE_ID)
        item["audio_locale"] = None
        season = SeasonData(item)

        assert router.build_path(season.get_info()) == f"/series/{SERIES_ID}/{DE_ID}"

    def test_create_path_from_named_route(self):
        path = router.create_path_from_route(
            "season_view_audio", {"series_id": "S1", "season_id": DE_ID, "audio_locale": "de-DE"}
        )

        assert path == f"/series/S1/{DE_ID}/audio/de-DE"
