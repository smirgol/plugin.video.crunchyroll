"""Tests for resolving the next episode: EpisodeData fields, pick_next_episode and fetch_next_episode."""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from resources.lib.models.content import EpisodeData, MovieData
from resources.lib.next_episode.resolver import fetch_next_episode, pick_next_episode
from resources.lib.utils.language import LanguagePreferences

FIXTURES = Path(__file__).parent.parent / "fixtures"
EPISODES_ENDPOINT = "https://www.crunchyroll.com/content/v2/cms/seasons/{}/episodes"

JA = "episodes_GYE5CQNJ2_V2"
DE = "episodes_GY19CPGQ9_V3"

_VERSION_RESPONSES = json.loads((FIXTURES / "version_responses.json").read_text(encoding="utf-8"))
_PROBE_RESPONSES = json.loads((FIXTURES / "probe_responses.json").read_text(encoding="utf-8"))


def _items(key):
    return copy.deepcopy(_VERSION_RESPONSES[key]["response"]["data"])


def _object_item():
    return copy.deepcopy(_PROBE_RESPONSES["objects"]["response"]["data"][0])


def _episodes(items):
    return [EpisodeData(item) for item in items]


def _prefs(filter_enabled):
    return LanguagePreferences(
        subtitle="de-DE",
        subtitle_fallback=None,
        filter_enabled=filter_enabled,
        show_dubs=True,
        show_dubs_fallback=False,
        show_subs=False,
    )


class TestEpisodeDataFields:
    def test_episode_reads_next_episode_id_and_availability(self):
        episode = EpisodeData(_items(JA)[0])

        assert episode.next_episode_id == "GG1UX5ZQX"
        assert episode.availability_status == "available"

    def test_object_item_has_no_next_episode_id(self):
        episode = EpisodeData(_object_item())

        assert episode.next_episode_id is None


class TestPickNextEpisode:
    def test_first_to_second_episode_ja(self):
        episodes = _episodes(_items(JA))

        result = pick_next_episode(episodes, episodes[0], _prefs(False))

        assert result.id == "GG1UX5ZQX"
        assert result.title == "TO BE HERO X - S01E02 - Xiao Yueqing"
        assert result.tvshowtitle == "TO BE HERO X"
        assert result.stream_id == "GG1UX5ZQXV"
        assert result.audio_locale == "ja-JP"
        assert result.season_id == "GYE5CQNJ2"
        assert result.thumb.endswith("61defca00938333d1aef846fa961bf2f.png")

    def test_first_to_second_episode_de(self):
        episodes = _episodes(_items(DE))

        result = pick_next_episode(episodes, episodes[0], _prefs(False))

        assert result.id == "GWDU7MQD1"
        assert result.stream_id == "GWDU7MQD1V"
        assert result.audio_locale == "de-DE"

    def test_last_episode_returns_none(self):
        episodes = _episodes(_items(JA))

        assert pick_next_episode(episodes, episodes[23], _prefs(False)) is None

    def test_next_id_not_in_list_returns_none(self):
        items = _items(DE)
        items[0]["next_episode_id"] = "XXXXXXXXX"
        episodes = _episodes(items)

        assert pick_next_episode(episodes, episodes[0], _prefs(False)) is None

    def test_missing_next_episode_id_returns_none(self):
        items = _items(JA)
        del items[0]["next_episode_id"]
        episodes = _episodes(items)

        assert pick_next_episode(episodes, episodes[0], _prefs(False)) is None

    def test_current_not_in_list_returns_none(self):
        current = _episodes(_items(DE))[0]
        episodes = _episodes(_items(JA))

        assert pick_next_episode(episodes, current, _prefs(False)) is None

    def test_unavailable_candidate_returns_none(self):
        items = _items(JA)
        items[1]["availability_status"] = "unavailable"
        episodes = _episodes(items)

        assert pick_next_episode(episodes, episodes[0], _prefs(False)) is None

    def test_candidate_without_stream_id_returns_none(self):
        episodes = _episodes(_items(JA))
        episodes[1].stream_id = None

        assert pick_next_episode(episodes, episodes[0], _prefs(False)) is None

    def test_missing_availability_status_is_accepted(self):
        items = _items(JA)
        del items[1]["availability_status"]
        episodes = _episodes(items)

        result = pick_next_episode(episodes, episodes[0], _prefs(False))

        assert result.id == "GG1UX5ZQX"

    def test_audio_rule_a_same_language_unchanged(self):
        episodes = _episodes(_items(JA))

        result = pick_next_episode(episodes, episodes[0], _prefs(True))

        assert result.id == "GG1UX5ZQX"
        assert result.audio_locale == "ja-JP"

    def test_audio_rule_b_dub_gap_switches_to_own_language(self):
        items = _items(DE)
        items[1] = _items(JA)[1]
        items[0]["next_episode_id"] = "GG1UX5ZQX"
        episodes = _episodes(items)

        result = pick_next_episode(episodes, episodes[0], _prefs(False))

        assert result.id == "GWDU7MQD1"
        assert result.episode_id == "GWDU7MQD1"
        assert result.stream_id == "GWDU7MQD1V"
        assert result.audio_locale == "de-DE"
        assert result.season_id == "GY19CPGQ9"

    def test_audio_rule_c_filter_picks_wanted_version(self):
        episodes = _episodes(_items(JA))
        episodes[0].audio_locale = "it-IT"

        result = pick_next_episode(episodes, episodes[0], _prefs(True))

        assert result.id == "GWDU7MQD1"
        assert result.audio_locale == "de-DE"

    def test_audio_rule_d_filter_off_unchanged(self):
        episodes = _episodes(_items(JA))
        episodes[0].audio_locale = "it-IT"

        result = pick_next_episode(episodes, episodes[0], _prefs(False))

        assert result.id == "GG1UX5ZQX"
        assert result.audio_locale == "ja-JP"

    def test_current_without_audio_uses_filter(self):
        episodes = _episodes(_items(JA))
        episodes[0].audio_locale = None

        result = pick_next_episode(episodes, episodes[0], _prefs(True))

        assert result.audio_locale == "de-DE"


class TestFetchNextEpisode:
    @pytest.fixture(autouse=True)
    def _settings(self, ctx, monkeypatch):
        monkeypatch.setattr(ctx.args, "subtitle", "de-DE")
        monkeypatch.setattr(ctx.args, "subtitle_fallback", None)
        monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: "false")
        ctx.api.EPISODES_ENDPOINT = EPISODES_ENDPOINT

    @staticmethod
    def _current():
        return EpisodeData(_object_item())

    def test_fetch_makes_one_request_with_current_audio(self, ctx):
        ctx.api.make_request.return_value = {"data": _items(JA), "total": 24}

        result = fetch_next_episode(ctx, self._current())

        ctx.api.make_request.assert_called_once_with(
            method="GET",
            url="https://www.crunchyroll.com/content/v2/cms/seasons/GYE5CQNJ2/episodes",
            params={"locale": "de-DE", "preferred_audio_language": "ja-JP"},
        )
        assert result.id == "GG1UX5ZQX"

    def test_fetch_reads_items_key(self, ctx):
        ctx.api.make_request.return_value = {"items": _items(JA)}

        result = fetch_next_episode(ctx, self._current())

        assert result.id == "GG1UX5ZQX"

    def test_fetch_without_audio_omits_preferred_audio(self, ctx):
        ctx.api.make_request.return_value = {"data": _items(JA)}
        current = self._current()
        current.audio_locale = None

        fetch_next_episode(ctx, current)

        assert ctx.api.make_request.call_args.kwargs["params"] == {"locale": "de-DE"}

    @pytest.mark.parametrize("response", [{"error": "x"}, None])
    def test_fetch_error_response_returns_none(self, ctx, response):
        ctx.api.make_request.return_value = response

        assert fetch_next_episode(ctx, self._current()) is None

    def test_fetch_exception_returns_none(self, ctx):
        ctx.api.make_request.side_effect = RuntimeError("net")

        assert fetch_next_episode(ctx, self._current()) is None

    def test_fetch_parse_error_returns_none(self, ctx):
        items = _items(JA)
        del items[3]["streams_link"]
        ctx.api.make_request.return_value = {"data": items}

        assert fetch_next_episode(ctx, self._current()) is None

    def test_fetch_movie_makes_no_request(self, ctx):
        assert fetch_next_episode(ctx, MagicMock(spec=MovieData)) is None

        ctx.api.make_request.assert_not_called()

    def test_fetch_none_makes_no_request(self, ctx):
        assert fetch_next_episode(ctx, None) is None

        ctx.api.make_request.assert_not_called()

    def test_fetch_without_season_id_makes_no_request(self, ctx):
        current = self._current()
        current.season_id = None

        assert fetch_next_episode(ctx, current) is None

        ctx.api.make_request.assert_not_called()
