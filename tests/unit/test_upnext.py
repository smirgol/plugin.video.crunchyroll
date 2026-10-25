"""Unit tests for the Up Next integration (resources/lib/upnext.py) and its hooks in VideoPlayer."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest

from resources.lib import upnext
from resources.lib.models.content import EpisodeData
from resources.lib.models.exceptions import CrunchyrollError
from resources.lib.videoplayer import VideoPlayer


def _episode(episode_id, number, season_id="S1", audio="ja-JP", duration=1440):
    return EpisodeData(
        {
            "id": episode_id,
            "title": f"Title {number}",
            "description": "plot",
            "episode_metadata": {
                "series_id": "SER",
                "series_title": "Show",
                "season_id": season_id,
                "season_number": 1,
                "episode_number": number,
                "duration_ms": duration * 1000,
                "audio_locale": audio,
                "episode_air_date": "2024-01-02T00:00:00",
            },
            "__links__": {"streams": {"href": f"/videos/{episode_id}V/streams"}},
        }
    )


@pytest.fixture
def settings(ctx):
    values = {}
    ctx.args.addon.getSetting.side_effect = lambda key: values.get(key, "")
    return values


@pytest.fixture
def installed():
    with patch.object(upnext, "is_upnext_installed", return_value=True) as mock:
        with patch.object(upnext, "supports_skip_segments", return_value=True):
            yield mock


def _episodes_response(season_episodes):
    return {"data": [{"id": e.id} for e in season_episodes]}


@pytest.fixture
def lookup(ctx):
    """Route episodes / seasons requests to canned listables."""
    state = {"episodes": {}, "seasons": []}

    def make_request(method, url, params=None):
        if url == ctx.api.SEASONS_ENDPOINT.format("SER"):
            return {"data": state["seasons"]}
        for season_id, episodes in state["episodes"].items():
            if url == ctx.api.EPISODES_ENDPOINT.format(season_id):
                return {"data": episodes}
        return {"error": "x"}

    ctx.api.make_request.side_effect = make_request
    ctx.api.SEASONS_ENDPOINT = "seasons/{}"
    ctx.api.EPISODES_ENDPOINT = "episodes/{}"
    ctx.args.subtitle = "en-US"

    def listables(data, item_type_hint=None, args=None):
        for item in data:
            if isinstance(item, Exception):
                raise item
        return list(data)

    with patch.object(upnext, "get_listables_from_response", side_effect=listables):
        yield state


class TestFindNextEpisode:
    def test_returns_following_episode_in_season(self, ctx, lookup):
        e1, e2 = _episode("E1", 1), _episode("E2", 2)
        lookup["episodes"]["S1"] = [e1, e2]

        assert upnext.find_next_episode(ctx, e1) is e2

    def test_skips_episodes_without_stream_id(self, ctx, lookup):
        e1, e2, e3 = _episode("E1", 1), _episode("E2", 2), _episode("E3", 3)
        e2.stream_id = None
        lookup["episodes"]["S1"] = [e1, e2, e3]

        assert upnext.find_next_episode(ctx, e1) is e3

    def test_unplayable_item_does_not_abort_lookup(self, ctx, lookup):
        e1, e3 = _episode("E1", 1), _episode("E3", 3)
        lookup["episodes"]["S1"] = [e1, CrunchyrollError("Failed to get stream id"), e3]

        assert upnext.find_next_episode(ctx, e1) is e3

    def test_ignores_other_audio_versions(self, ctx, lookup):
        e1, other, e2 = _episode("E1", 1), _episode("X", 2, audio="de-DE"), _episode("E2", 2)
        lookup["episodes"]["S1"] = [e1, other, e2]

        assert upnext.find_next_episode(ctx, e1) is e2

    def test_crosses_into_next_season_in_same_audio(self, ctx, lookup):
        last = _episode("E1", 1)
        first_of_next = _episode("N1", 1, season_id="S2")
        lookup["episodes"] = {"S1": [last], "S2B": [first_of_next]}
        lookup["seasons"] = [
            {"id": "S1", "audio_locale": "ja-JP"},
            {
                "id": "S2",
                "versions": [
                    {"guid": "S2A", "audio_locale": "de-DE", "original": False},
                    {"guid": "S2B", "audio_locale": "ja-JP", "original": True},
                ],
            },
        ]

        assert upnext.find_next_episode(ctx, last) is first_of_next

    def test_series_finale_has_no_next_episode(self, ctx, lookup):
        last = _episode("E1", 1)
        lookup["episodes"]["S1"] = [last]
        lookup["seasons"] = [{"id": "S1", "audio_locale": "ja-JP"}]

        assert upnext.find_next_episode(ctx, last) is None

    def test_request_error_yields_none(self, ctx, lookup):
        assert upnext.find_next_episode(ctx, _episode("E1", 1)) is None


class TestPayload:
    def test_contains_required_keys(self):
        payload = upnext.build_payload(_episode("E1", 1), _episode("E2", 2), "plugin://x/play")

        assert payload["play_url"] == "plugin://x/play"
        for key in ("current_episode", "next_episode"):
            episode = payload[key]
            assert {
                "episodeid",
                "tvshowid",
                "title",
                "art",
                "season",
                "episode",
                "showtitle",
                "plot",
                "playcount",
                "rating",
                "firstaired",
                "runtime",
            } <= set(episode)
        assert payload["current_episode"]["episodeid"] == "E1"
        assert payload["next_episode"]["tvshowid"] == "SER"
        assert payload["next_episode"]["firstaired"] == "2024-01-02"
        assert "notification_offset" not in payload
        assert "skip_segments" not in payload

    def test_timing_included_when_requested(self):
        skip = {"credits": {"start": 1300, "end": 1440}, "intro": {"start": 60, "end": 120}}

        payload = upnext.build_payload(
            _episode("E1", 1), _episode("E2", 2), "u", skip_events=skip, use_skip_events=True
        )

        assert payload["notification_offset"] == 1300
        assert payload["skip_segments"] == [{"kind": "intro", "start": 60, "end": 120}]

    def test_timing_left_out_when_not_requested(self):
        skip = {"credits": {"start": 1300, "end": 1440}}

        payload = upnext.build_payload(_episode("E1", 1), _episode("E2", 2), "u", skip_events=skip)

        assert "notification_offset" not in payload

    def test_invalid_credits_start_is_ignored(self):
        skip = {"credits": {"start": 99999, "end": 100000}}

        payload = upnext.build_payload(
            _episode("E1", 1), _episode("E2", 2), "u", skip_events=skip, use_skip_events=True
        )

        assert "notification_offset" not in payload


class TestSendPayload:
    def test_sends_base64_json_rpc_notification(self):
        with patch.object(upnext.xbmc, "executeJSONRPC", return_value='{"result": "OK"}') as rpc:
            assert upnext.send_payload("plugin.video.crunchyroll", {"a": 1}) is True

        request = json.loads(rpc.call_args[0][0])
        assert request["method"] == "JSONRPC.NotifyAll"
        assert request["params"]["sender"] == "plugin.video.crunchyroll.SIGNAL"
        assert request["params"]["message"] == "upnext_data"
        assert json.loads(base64.b64decode(request["params"]["data"][0])) == {"a": 1}

    def test_failure_response_returns_false(self):
        with patch.object(upnext.xbmc, "executeJSONRPC", return_value='{"error": {}}'):
            assert upnext.send_payload("plugin.video.crunchyroll", {}) is False


class TestSettingsGating:
    def test_replaces_native_skip_requires_both_settings_and_addon(self, ctx, settings):
        settings.update(enable_upnext="true", upnext_replace_skip="true")
        with patch.object(upnext, "is_upnext_installed", return_value=True):
            with patch.object(upnext, "supports_skip_segments", return_value=True):
                assert upnext.replaces_native_skip(ctx.args) is True
        with patch.object(upnext, "is_upnext_installed", return_value=False):
            assert upnext.replaces_native_skip(ctx.args) is False

        settings["upnext_replace_skip"] = "false"
        with patch.object(upnext, "is_upnext_installed", return_value=True):
            assert upnext.replaces_native_skip(ctx.args) is False

        settings.update(enable_upnext="false", upnext_replace_skip="true")
        with patch.object(upnext, "is_upnext_installed", return_value=True):
            assert upnext.replaces_native_skip(ctx.args) is False

    def test_old_upnext_keeps_native_skip(self, ctx, settings):
        settings.update(enable_upnext="true", upnext_replace_skip="true")
        with patch.object(upnext, "is_upnext_installed", return_value=True):
            with patch.object(upnext, "supports_skip_segments", return_value=False):
                assert upnext.replaces_native_skip(ctx.args) is False

    @pytest.mark.parametrize("version,expected", [("1.3.0", True), ("1.2.3", False), ("1.10.0", True), ("x", False)])
    def test_supports_skip_segments_by_version(self, version, expected):
        with patch.object(upnext.xbmcaddon, "Addon") as addon:
            addon.return_value.getAddonInfo.return_value = version
            assert upnext.supports_skip_segments() is expected


@pytest.fixture
def player(ctx):
    with patch("resources.lib.videoplayer.xbmc.Player"):
        instance = VideoPlayer(ctx)
    instance.isPlaying = MagicMock(return_value=True)
    instance._stream_data = MagicMock()
    return instance


class TestVideoPlayerHook:
    def test_does_nothing_when_disabled(self, player, settings):
        with patch.object(upnext, "notify_next_episode") as notify:
            player.notify_upnext()
        notify.assert_not_called()

    def test_notifies_once_when_enabled(self, player, settings, installed):
        settings["enable_upnext"] = "true"
        with patch.object(upnext, "notify_next_episode") as notify:
            player.notify_upnext()
            player.notify_upnext()
        notify.assert_called_once()

    def test_waits_until_playing(self, player, settings, installed):
        settings["enable_upnext"] = "true"
        player.isPlaying.return_value = False
        with patch.object(upnext, "notify_next_episode") as notify:
            player.notify_upnext()
        notify.assert_not_called()
        assert player.upnext_handled is False

    def test_warns_when_addon_missing(self, player, settings):
        settings["enable_upnext"] = "true"
        with patch.object(upnext, "is_upnext_installed", return_value=False), patch.object(
            upnext, "notify_next_episode"
        ) as notify, patch("resources.lib.videoplayer.xbmcgui.Dialog") as dialog:
            player.notify_upnext()
        notify.assert_not_called()
        dialog.return_value.notification.assert_called_once()

    def test_errors_do_not_propagate(self, player, settings, installed):
        settings["enable_upnext"] = "true"
        with patch.object(upnext, "notify_next_episode", side_effect=RuntimeError("boom")):
            player.notify_upnext()

    def test_native_skip_is_disabled_while_upnext_replaces_it(self, player, settings, installed):
        settings.update(enable_upnext="true", upnext_replace_skip="true", ask_before_skipping="false")
        player._stream_data.skip_events_data = {"intro": {"start": 0, "end": 100}}
        player._player.getTime.return_value = 10
        player._instaskip = MagicMock()

        player.check_skipping()

        player._instaskip.assert_not_called()

    def test_native_skip_still_used_by_default(self, player, settings):
        settings.update(ask_before_skipping="false")
        player._stream_data.skip_events_data = {"intro": {"start": 0, "end": 100}}
        player._player.getTime.return_value = 10
        player._instaskip = MagicMock()

        player.check_skipping()

        player._instaskip.assert_called_once_with("intro")
