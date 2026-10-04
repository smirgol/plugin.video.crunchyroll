"""Unit tests for the season playlist queued on playback (native next/previous + auto play next)."""

import json
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from resources.lib import controller
from resources.lib.models.content import EpisodeData


def _episode(n: int) -> EpisodeData:
    return EpisodeData(
        {
            "id": f"EP{n}",
            "title": f"Episode {n}",
            "series_id": "SERIES",
            "season_id": "SEASON",
            "series_title": "Show",
            "season_number": 1,
            "episode_number": n,
            "duration_ms": 1440000,
            "streams_link": f"/content/v2/cms/videos/STREAM{n}/streams",
        }
    )


@pytest.fixture
def season(ctx):
    """Season of 4 episodes, EP3 being played from a single item playlist."""
    episodes = [_episode(n) for n in range(1, 5)]
    ctx.args.addonurl = "plugin://plugin.video.crunchyroll"
    ctx.args.get_arg = lambda key, default=None: {"episode_id": "EP3"}.get(key, default)

    video_player = MagicMock()
    video_player.stream_data.playable_item.season_id = "SEASON"

    playlist = MagicMock()
    playlist.size.return_value = 1

    with ExitStack() as stack:
        fetch = stack.enter_context(patch.object(controller, "fetch_season_episodes", return_value=episodes))
        stack.enter_context(patch.object(controller.view, "complement_listables", new=MagicMock()))
        stack.enter_context(patch.object(controller.asyncio, "run"))
        stack.enter_context(patch.object(controller.xbmc, "PlayList", return_value=playlist))
        stack.enter_context(patch.object(controller.xbmc, "PLAYLIST_VIDEO", 1))
        rpc = stack.enter_context(patch.object(controller.xbmc, "executeJSONRPC", return_value='{"result":"OK"}'))
        yield {"ctx": ctx, "player": video_player, "playlist": playlist, "fetch": fetch, "rpc": rpc}


class TestFillSeasonPlaylist:
    def test_queues_other_episodes_with_listing_urls(self, season):
        controller.fill_season_playlist(season["ctx"], season["player"])

        urls = [c.args[0] for c in season["playlist"].add.call_args_list]
        assert len(urls) == 3
        assert urls[0].startswith("plugin://plugin.video.crunchyroll/video/SERIES/EP1/")
        assert "/EP3/" not in "".join(urls)
        season["fetch"].assert_called_once_with(season["ctx"], "SEASON")

    def test_moves_current_episode_to_its_season_position(self, season):
        result = controller.fill_season_playlist(season["ctx"], season["player"])

        assert result[0] == 2 and result[1].episode_id == "EP3" and result[2] == 4

        swaps = [json.loads(c.args[0])["params"] for c in season["rpc"].call_args_list]
        assert [(s["position1"], s["position2"]) for s in swaps] == [(0, 1), (1, 2)]

    def test_stops_swapping_on_rpc_error(self, season):
        season["rpc"].return_value = '{"error":{"code":-32602}}'
        controller.fill_season_playlist(season["ctx"], season["player"])

        assert season["rpc"].call_count == 1

    def test_skips_when_already_in_a_playlist(self, season):
        season["playlist"].size.return_value = 4
        controller.fill_season_playlist(season["ctx"], season["player"])

        season["fetch"].assert_not_called()
        season["playlist"].add.assert_not_called()

    def test_skips_when_episode_not_in_season(self, season):
        season["ctx"].args.get_arg = lambda key, default=None: {"episode_id": "OTHER"}.get(key, default)
        controller.fill_season_playlist(season["ctx"], season["player"])

        season["playlist"].add.assert_not_called()

    def test_skips_on_api_error(self, season):
        season["fetch"].return_value = None
        controller.fill_season_playlist(season["ctx"], season["player"])

        season["playlist"].add.assert_not_called()


class TestStartPlaybackQueuesSeason:
    @pytest.mark.parametrize("setting, expected_calls", [("true", 1), ("", 1), ("false", 0)])
    @patch.object(controller, "fill_season_playlist")
    @patch.object(controller, "VideoPlayer")
    def test_respects_setting(self, player_class, fill, ctx, setting, expected_calls):
        ctx.args.addon.getSetting = lambda key: setting if key == "season_playlist" else "false"
        player_class.return_value.isStartingOrPlaying.return_value = False

        controller.start_playback(ctx)

        assert fill.call_count == expected_calls

    @patch.object(controller, "fill_season_playlist", side_effect=RuntimeError("boom"))
    @patch.object(controller, "VideoPlayer")
    def test_failure_does_not_break_playback(self, player_class, fill, ctx):
        ctx.args.addon.getSetting = lambda key: "true"
        player_class.return_value.isStartingOrPlaying.return_value = False

        controller.start_playback(ctx)

        player_class.return_value.finished.assert_called_once()


class TestRefreshLaunchedEntry:
    def test_replaces_stale_entry_with_a_fresh_copy(self, season):
        season["playlist"].size.return_value = 4
        controller.refresh_launched_entry(season["ctx"], 1, _episode(2), 4)

        assert (
            season["playlist"].add.call_args.args[0].startswith("plugin://plugin.video.crunchyroll/video/SERIES/EP2/")
        )
        requests = [json.loads(c.args[0]) for c in season["rpc"].call_args_list]
        calls = [(r["method"], r["params"]) for r in requests]
        assert calls[0] == ("Playlist.Remove", {"playlistid": 1, "position": 1})
        # fresh copy bubbles up from the end (index 3 after the removal) to position 1
        assert [(p["position1"], p["position2"]) for _, p in calls[1:]] == [(2, 3), (1, 2)]

    def test_drops_the_copy_when_stale_entry_is_still_playing(self, season):
        season["playlist"].size.return_value = 4
        season["rpc"].side_effect = ['{"error":{"code":-32602}}', '{"result":"OK"}']
        controller.refresh_launched_entry(season["ctx"], 1, _episode(2), 4)

        params = [json.loads(c.args[0])["params"] for c in season["rpc"].call_args_list]
        assert params[1] == {"playlistid": 1, "position": 4}

    def test_skips_when_playlist_was_replaced(self, season):
        season["playlist"].size.return_value = 1
        controller.refresh_launched_entry(season["ctx"], 1, _episode(2), 4)

        season["playlist"].add.assert_not_called()
        season["rpc"].assert_not_called()
