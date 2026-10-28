"""Tests for should_offer_next_episode."""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from resources.lib import presentation
from resources.lib.models.content import EpisodeData
from resources.lib.next_episode import prompt
from resources.lib.next_episode.countdown import ChoiceLatch, NextEpisodeChoice
from resources.lib.next_episode.prompt import should_offer_next_episode

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.mark.parametrize("ended_regularly", [True, False])
@pytest.mark.parametrize("abort_requested", [True, False])
@pytest.mark.parametrize("has_next_episode", [True, False])
def test_should_offer_next_episode_table(ended_regularly, abort_requested, has_next_episode):
    next_episode = MagicMock(spec=EpisodeData) if has_next_episode else None

    expected = ended_regularly and not abort_requested and has_next_episode

    assert should_offer_next_episode(ended_regularly, abort_requested, next_episode) is expected


def _next_episode() -> EpisodeData:
    data = json.loads((FIXTURES / "version_responses.json").read_text(encoding="utf-8"))
    return EpisodeData(copy.deepcopy(data["episodes_GYE5CQNJ2_V2"]["response"]["data"][1]))


class _Harness:
    """Records Kodi-side events and lets a test script what happens while the dialog is modal."""

    def __init__(self):
        self.events = []
        self.instances = []
        self.on_modal = None


@pytest.fixture
def harness(monkeypatch, ctx):
    harness = _Harness()

    class FakeDialog:
        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs
            self.tick_thread = MagicMock()
            harness.instances.append(self)

        def doModal(self):
            harness.events.append("doModal")
            if harness.on_modal is not None:
                harness.on_modal(self)

    monkeypatch.setattr("resources.lib.next_episode.prompt.NextEpisodeDialog", FakeDialog)
    monkeypatch.setattr("resources.lib.next_episode.prompt.xbmc.executebuiltin", lambda cmd: harness.events.append(cmd))
    monkeypatch.setattr(ctx.args.addon, "getSettingInt", lambda name: 15)
    monkeypatch.setattr(ctx.args.addon, "getAddonInfo", lambda key: "/addon")
    ctx.monitor.abortRequested.return_value = False
    return harness


def _tick_until_finished(dialog):
    countdown = dialog.kwargs["countdown"]
    while not countdown.is_finished:
        countdown.tick()


class TestOfferNextEpisode:
    def test_offer_cancels_skip_alarm_before_modal(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["countdown"].confirm()

        prompt.offer_next_episode(ctx, _next_episode())

        assert harness.events[:2] == ["CancelAlarm(closedialog,true)", "doModal"]

    def test_offer_returns_continue_on_confirm(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["countdown"].confirm()

        assert prompt.offer_next_episode(ctx, _next_episode()) is NextEpisodeChoice.CONTINUE

    def test_offer_returns_timeout_on_expiry(self, ctx, harness):
        harness.on_modal = _tick_until_finished

        assert prompt.offer_next_episode(ctx, _next_episode()) is NextEpisodeChoice.TIMEOUT

    def test_offer_returns_cancel_on_cancel(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["countdown"].cancel()

        assert prompt.offer_next_episode(ctx, _next_episode()) is NextEpisodeChoice.CANCEL

    def test_offer_without_decision_returns_cancel(self, ctx, harness):
        harness.on_modal = None

        assert prompt.offer_next_episode(ctx, _next_episode()) is NextEpisodeChoice.CANCEL

    def test_offer_abort_returns_cancel(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["countdown"].confirm()
        ctx.monitor.abortRequested.return_value = True

        assert prompt.offer_next_episode(ctx, _next_episode()) is NextEpisodeChoice.CANCEL

    def test_offer_joins_tick_thread_before_return(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["countdown"].confirm()

        prompt.offer_next_episode(ctx, _next_episode())

        dialog = harness.instances[0]
        dialog.tick_thread.join.assert_called_once_with(timeout=2.0)
        assert dialog.kwargs["stop_event"].is_set()

    def test_offer_stops_ticks_when_modal_raises(self, ctx, harness):
        def raise_error(dialog):
            raise RuntimeError("boom")

        harness.on_modal = raise_error

        with pytest.raises(RuntimeError):
            prompt.offer_next_episode(ctx, _next_episode())

        dialog = harness.instances[0]
        assert dialog.kwargs["stop_event"].is_set()
        dialog.tick_thread.join.assert_called_once_with(timeout=2.0)

    def test_offer_passes_episode_texts_and_labels(self, ctx, harness):
        prompt.offer_next_episode(ctx, _next_episode())

        dialog = harness.instances[0]
        assert dialog.args == ("plugin-video-crunchyroll-next-episode.xml", "/addon", "default", "1080i")
        assert dialog.kwargs["series_title"] == "TO BE HERO X"
        assert dialog.kwargs["episode_title"] == "S01E02 - Xiao Yueqing"
        assert dialog.kwargs["thumb"].endswith("61defca00938333d1aef846fa961bf2f.png")
        assert dialog.kwargs["labels"] == prompt.NextEpisodeLabels(
            "String_30502", "String_30503", "String_30504", "String_30505"
        )

    def test_offer_formats_episode_title_from_fields(self, ctx, harness):
        episode = _next_episode()
        episode.episode = None

        prompt.offer_next_episode(ctx, episode)

        assert harness.instances[0].kwargs["episode_title"] == "S01 - Xiao Yueqing"

    def test_offer_uses_countdown_setting(self, ctx, harness, monkeypatch):
        monkeypatch.setattr(ctx.args.addon, "getSettingInt", lambda name: 30)

        prompt.offer_next_episode(ctx, _next_episode())

        assert harness.instances[0].kwargs["countdown"].remaining == 30

    def test_offer_thumb_none_becomes_empty_string(self, ctx, harness):
        episode = _next_episode()
        episode.thumb = None

        prompt.offer_next_episode(ctx, episode)

        assert harness.instances[0].kwargs["thumb"] == ""

    def test_offer_passes_countdown_decision(self, ctx, harness):
        prompt.offer_next_episode(ctx, _next_episode())

        dialog = harness.instances[0]
        assert dialog.kwargs["decision"] is dialog.kwargs["countdown"].decision

    def test_offer_result_follows_decision(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["decision"].confirm()

        assert prompt.offer_next_episode(ctx, _next_episode()) is NextEpisodeChoice.CONTINUE


class TestAskStillWatching:
    def test_ask_passes_no_countdown_and_open_decision(self, ctx, harness):
        seen = []
        harness.on_modal = lambda d: seen.append(d.kwargs["decision"].result)

        prompt.ask_still_watching(ctx, _next_episode())

        kwargs = harness.instances[0].kwargs
        assert kwargs["countdown"] is None
        assert isinstance(kwargs["decision"], ChoiceLatch)
        assert seen == [None]

    def test_ask_uses_still_watching_header(self, ctx, harness):
        prompt.ask_still_watching(ctx, _next_episode())

        assert harness.instances[0].kwargs["labels"] == prompt.NextEpisodeLabels(
            "String_30506", "String_30503", "String_30504", "String_30505"
        )

    def test_ask_passes_episode_texts(self, ctx, harness):
        prompt.ask_still_watching(ctx, _next_episode())

        dialog = harness.instances[0]
        assert dialog.args == ("plugin-video-crunchyroll-next-episode.xml", "/addon", "default", "1080i")
        assert dialog.kwargs["series_title"] == "TO BE HERO X"
        assert dialog.kwargs["episode_title"] == "S01E02 - Xiao Yueqing"

    def test_ask_returns_continue_on_confirm(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["decision"].confirm()

        assert prompt.ask_still_watching(ctx, _next_episode()) is NextEpisodeChoice.CONTINUE

    def test_ask_returns_cancel_on_cancel(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["decision"].cancel()

        assert prompt.ask_still_watching(ctx, _next_episode()) is NextEpisodeChoice.CANCEL

    def test_ask_without_decision_returns_cancel(self, ctx, harness):
        harness.on_modal = None

        assert prompt.ask_still_watching(ctx, _next_episode()) is NextEpisodeChoice.CANCEL

    def test_ask_abort_returns_cancel(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["decision"].confirm()
        ctx.monitor.abortRequested.return_value = True

        assert prompt.ask_still_watching(ctx, _next_episode()) is NextEpisodeChoice.CANCEL

    def test_ask_cancels_skip_alarm_before_modal(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["decision"].confirm()

        prompt.ask_still_watching(ctx, _next_episode())

        assert harness.events[:2] == ["CancelAlarm(closedialog,true)", "doModal"]

    def test_ask_joins_thread_and_sets_stop_event(self, ctx, harness):
        harness.on_modal = lambda d: d.kwargs["decision"].confirm()

        prompt.ask_still_watching(ctx, _next_episode())

        dialog = harness.instances[0]
        dialog.tick_thread.join.assert_called_once_with(timeout=2.0)
        assert dialog.kwargs["stop_event"].is_set()

    def test_ask_does_not_read_countdown_setting(self, ctx, harness, monkeypatch):
        get_setting_int = MagicMock()
        monkeypatch.setattr(ctx.args.addon, "getSettingInt", get_setting_int)

        prompt.ask_still_watching(ctx, _next_episode())

        get_setting_int.assert_not_called()

    def test_ask_logs_result(self, ctx, harness, monkeypatch):
        records = []
        monkeypatch.setattr(prompt, "crunchy_log", lambda message, level=None: records.append((message, level)))
        harness.on_modal = lambda d: d.kwargs["decision"].confirm()

        prompt.ask_still_watching(ctx, _next_episode())

        assert ("next episode dialog result: continue", prompt.xbmc.LOGINFO) in records


ADDON_URL = "plugin://plugin.video.crunchyroll"
NEXT_EPISODE_URL = f"{ADDON_URL}/video/GQWH0M1J3/GG1UX5ZQX/GG1UX5ZQXV"


class TestStartEpisode:
    def test_next_episode_url_matches_list_url(self):
        episode = _next_episode()

        url = prompt.next_episode_url(episode, ADDON_URL)

        assert url == NEXT_EPISODE_URL
        assert url == presentation.build_url(episode.get_info(), ADDON_URL)

    # PlayMedia(<url>) without quotes is only safe because the URL consists solely of alphanumeric ids and "/"
    # (no comma, which Kodi would read as an argument separator).
    def test_start_episode_uses_playmedia_without_wait(self, ctx, monkeypatch):
        fake_xbmc = MagicMock()
        monkeypatch.setattr("resources.lib.next_episode.prompt.xbmc", fake_xbmc)
        monkeypatch.setattr(ctx.args, "addonurl", ADDON_URL)

        prompt.start_episode(ctx, _next_episode())

        assert fake_xbmc.executebuiltin.call_args_list == [call(f"PlayMedia({NEXT_EPISODE_URL})")]
        fake_xbmc.Player.assert_not_called()

    # Characterization/guard: already green before the implementation.
    def test_prompt_does_not_reference_playback_entry_points(self):
        assert not hasattr(prompt, "start_playback")
        assert not hasattr(prompt, "VideoPlayer")
