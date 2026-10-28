"""Unit tests for controller.start_playback: the stream is always released, original exceptions propagate."""

from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest

import resources.lib.controller as controller
from resources.lib.next_episode.countdown import NextEpisodeChoice


@pytest.fixture
def video_player(ctx, monkeypatch):
    player = MagicMock()
    monkeypatch.setattr(controller, "VideoPlayer", MagicMock(return_value=player))
    ctx.monitor.abortRequested.return_value = False
    monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: "false")
    return player


def test_finished_called_after_regular_loop_end(ctx, video_player):
    video_player.isStartingOrPlaying.side_effect = [True, False]

    controller.start_playback(ctx)

    video_player.finished.assert_called_once()
    video_player.check_skipping.assert_called_once()


def test_finished_called_when_loop_raises(ctx, video_player):
    video_player.isStartingOrPlaying.return_value = True
    video_player.check_skipping.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        controller.start_playback(ctx)

    video_player.finished.assert_called_once()


def test_finished_called_when_start_raises(ctx, video_player):
    video_player.start_playback.side_effect = RuntimeError("start")

    with pytest.raises(RuntimeError, match="start"):
        controller.start_playback(ctx)

    video_player.finished.assert_called_once()
    video_player.check_skipping.assert_not_called()


def _setup(ctx, monkeypatch, enabled=True, end_event=None, offer=NextEpisodeChoice.CONTINUE, next_episode=True):
    """Wire a fake player, end-listener and next-episode collaborators into the controller module.

    end_event: "ended", "stopped" or None (Kodi never reports an end).
    """
    vp = MagicMock()
    vp.isStartingOrPlaying.side_effect = [True, True, False]
    vp.playback_times.return_value = (200.0, 1440.0)
    vp.skip_events = {}
    monkeypatch.setattr(controller, "VideoPlayer", MagicMock(return_value=vp))

    ctx.monitor.abortRequested.return_value = False
    ctx.monitor.waitForAbort.return_value = False
    settings = {"enable_next_episode_dialog": "true" if enabled else "false", "sync_playtime": "false"}
    monkeypatch.setattr(ctx.args.addon, "getSetting", lambda name: settings.get(name, "false"))

    def make_listener(tracker):
        if end_event == "ended":
            tracker.on_ended()
        elif end_event == "stopped":
            tracker.on_stopped()
        return MagicMock()

    listener = MagicMock(side_effect=make_listener)
    episode = MagicMock(name="next")
    fetch = MagicMock(return_value=episode if next_episode else None)
    offer_mock = MagicMock(return_value=offer)
    start = MagicMock()
    monkeypatch.setattr(controller, "PlaybackEndListener", listener)
    monkeypatch.setattr(controller, "fetch_next_episode", fetch)
    monkeypatch.setattr(controller, "offer_next_episode", offer_mock)
    monkeypatch.setattr(controller, "start_episode", start)
    return SimpleNamespace(vp=vp, listener=listener, episode=episode, fetch=fetch, offer=offer_mock, start=start)


def test_disabled_feature_creates_no_listener_and_fetches_nothing(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, enabled=False, end_event="ended")

    controller.start_playback(ctx)

    s.listener.assert_not_called()
    s.fetch.assert_not_called()
    s.offer.assert_not_called()
    s.start.assert_not_called()
    s.vp.playback_times.assert_not_called()
    assert ctx.monitor.waitForAbort.call_args_list == [call(1), call(1)]
    s.vp.finished.assert_called_once()


def test_prefetch_happens_once_while_playing(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch)
    s.vp.isStartingOrPlaying.side_effect = [True, True, True, False]

    controller.start_playback(ctx)

    s.fetch.assert_called_once_with(ctx, s.vp.playable_item)
    assert s.vp.playback_times.call_count == 1


def test_no_prefetch_before_threshold(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="ended")
    s.vp.playback_times.return_value = (30.0, 1440.0)

    controller.start_playback(ctx)

    s.fetch.assert_not_called()
    s.offer.assert_not_called()


def test_no_prefetch_when_not_playing(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch)
    s.vp.playback_times.return_value = None

    controller.start_playback(ctx)

    s.fetch.assert_not_called()


def test_regular_end_offers_and_starts_on_continue(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="ended", offer=NextEpisodeChoice.CONTINUE)

    controller.start_playback(ctx)

    s.offer.assert_called_once_with(ctx, s.episode)
    s.start.assert_called_once_with(ctx, s.episode)


def test_timeout_starts_next_episode(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="ended", offer=NextEpisodeChoice.TIMEOUT)

    controller.start_playback(ctx)

    s.start.assert_called_once_with(ctx, s.episode)


def test_cancel_does_not_start(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="ended", offer=NextEpisodeChoice.CANCEL)

    controller.start_playback(ctx)

    s.offer.assert_called_once()
    s.start.assert_not_called()


def test_stop_shows_no_dialog(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="stopped")

    controller.start_playback(ctx)

    s.offer.assert_not_called()
    s.start.assert_not_called()


def test_abort_after_loop_shows_no_dialog(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="ended")
    finished = []
    s.vp.finished.side_effect = lambda: finished.append(True)
    ctx.monitor.abortRequested.side_effect = lambda: bool(finished)

    controller.start_playback(ctx)

    s.offer.assert_not_called()
    s.start.assert_not_called()


def test_no_next_episode_skips_pump_and_dialog(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, next_episode=False)
    s.vp.isStartingOrPlaying.side_effect = [True, True, True, True, False]

    controller.start_playback(ctx)

    assert s.fetch.call_count == 1
    s.offer.assert_not_called()
    assert all(c == call(1) for c in ctx.monitor.waitForAbort.call_args_list)


def test_offer_exception_is_logged_not_raised(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="ended")
    s.offer.side_effect = RuntimeError("skin")
    log_error = MagicMock()
    monkeypatch.setattr(controller, "log_error_with_trace", log_error)

    controller.start_playback(ctx)

    log_error.assert_called_once_with("Next episode dialog failed", show_notification=False)
    s.start.assert_not_called()
    s.vp.finished.assert_called_once()


def test_missing_end_event_pumps_then_shows_no_dialog(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event=None)

    controller.start_playback(ctx)

    assert ctx.monitor.waitForAbort.call_args_list[-4:] == [call(0.5)] * 4
    s.offer.assert_not_called()


def test_start_episode_is_last_action(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="ended", offer=NextEpisodeChoice.CONTINUE)
    events = []

    def record(name, result=None):
        def side_effect(*args, **kwargs):
            events.append(name)
            return result

        return side_effect

    s.vp.finished.side_effect = record("finished")
    ctx.monitor.waitForAbort.side_effect = record("wait", False)
    ctx.monitor.abortRequested.side_effect = record("abort_check", False)
    s.offer.side_effect = record("offer", NextEpisodeChoice.CONTINUE)
    s.start.side_effect = record("start_episode")

    controller.start_playback(ctx)

    assert events.index("finished") < events.index("offer") < events.index("start_episode")
    assert events[-1] == "start_episode"


def test_exception_in_loop_offers_nothing(ctx, monkeypatch):
    s = _setup(ctx, monkeypatch, end_event="ended")
    # round 1 prefetches the next episode, round 2 raises
    s.vp.isStartingOrPlaying.side_effect = [True, True, True, False]
    s.vp.check_skipping.side_effect = [None, RuntimeError("boom")]

    with pytest.raises(RuntimeError, match="boom"):
        controller.start_playback(ctx)

    assert s.fetch.call_count == 1
    s.vp.finished.assert_called_once()
    s.offer.assert_not_called()
    s.start.assert_not_called()


class FakeChainStore:
    def __init__(self, value, events, put_error=None):
        self.value, self.events, self.put_error = value, events, put_error
        self.put_values = []

    def take(self):
        self.events.append("take")
        value, self.value = self.value, ""
        return value

    def put(self, value):
        self.events.append("put")
        if self.put_error is not None:
            raise self.put_error
        self.put_values.append(value)


def _chain_setup(ctx, monkeypatch, stored="", current_id="EP1", limit=3, next_id="EP2", put_error=None, **kwargs):
    """_setup plus a fake chain store, a patched still-watching entry and stubbed id/limit."""
    s = _setup(ctx, monkeypatch, **kwargs)
    events = []
    store = FakeChainStore(stored, events, put_error)
    store_class = MagicMock(return_value=store)
    ask = MagicMock(return_value=NextEpisodeChoice.CONTINUE)
    log = MagicMock()
    monkeypatch.setattr(controller, "HomeWindowChainStore", store_class)
    monkeypatch.setattr(controller, "ask_still_watching", ask)
    monkeypatch.setattr(controller, "crunchy_log", log)
    monkeypatch.setattr(ctx.args, "get_arg", lambda name, *args, **kw: current_id if name == "episode_id" else None)
    monkeypatch.setattr(
        ctx.args.addon, "getSettingInt", lambda name: {"next_episode_still_watching_after": limit}.get(name, 15)
    )
    s.episode.episode_id = next_id
    s.vp.start_playback.side_effect = lambda: events.append("start_playback")
    s.start.side_effect = lambda *a: events.append("start_episode")
    return SimpleNamespace(**vars(s), store=store, store_class=store_class, ask=ask, log=log, events=events)


def _streak_log_lines(s):
    return [
        c.args[0] for c in s.log.call_args_list if c.args and str(c.args[0]).startswith("next episode: auto-continue")
    ]


def test_streak_below_limit_offers_countdown(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="2:EP1", limit=3, end_event="ended")

    controller.start_playback(ctx)

    s.offer.assert_called_once_with(ctx, s.episode)
    s.ask.assert_not_called()
    assert call("next episode: auto-continue streak 2/3", controller.xbmc.LOGINFO) in s.log.call_args_list
    assert _streak_log_lines(s) == ["next episode: auto-continue streak 2/3"]


def test_streak_at_limit_asks_still_watching(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="3:EP1", limit=3, end_event="ended")

    controller.start_playback(ctx)

    s.ask.assert_called_once_with(ctx, s.episode)
    s.offer.assert_not_called()
    expected = "next episode: auto-continue streak 3/3, asking whether still watching"
    assert call(expected, controller.xbmc.LOGINFO) in s.log.call_args_list
    assert _streak_log_lines(s) == [expected]
    s.start.assert_called_once_with(ctx, s.episode)


def test_limit_zero_never_asks(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="5:EP1", limit=0, end_event="ended")

    controller.start_playback(ctx)

    s.offer.assert_called_once_with(ctx, s.episode)
    s.ask.assert_not_called()


def test_handoff_for_other_episode_resets(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="3:OTHER", limit=3, end_event="ended")

    controller.start_playback(ctx)

    s.offer.assert_called_once_with(ctx, s.episode)
    s.ask.assert_not_called()
    assert call("next episode: auto-continue streak 0/3", controller.xbmc.LOGINFO) in s.log.call_args_list
    assert _streak_log_lines(s) == ["next episode: auto-continue streak 0/3"]


def test_unreadable_store_value_resets(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored=MagicMock(), limit=MagicMock(), end_event="ended")

    controller.start_playback(ctx)

    s.offer.assert_called_once_with(ctx, s.episode)
    assert call("next episode: auto-continue streak 0/3", controller.xbmc.LOGINFO) in s.log.call_args_list
    assert _streak_log_lines(s) == ["next episode: auto-continue streak 0/3"]


def test_handoff_is_taken_once_before_playback_starts(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="1:EP1", end_event="ended")

    controller.start_playback(ctx)

    assert s.events.count("take") == 1
    assert s.events.index("take") < s.events.index("start_playback")
    assert s.store.value == ""


def test_timeout_hands_over_incremented_streak_before_start(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="2:EP1", end_event="ended", offer=NextEpisodeChoice.TIMEOUT)

    controller.start_playback(ctx)

    assert s.store.put_values == ["3:EP2"]
    assert s.events.index("put") < s.events.index("start_episode")
    assert s.events[-1] == "start_episode"


def test_timeout_from_manual_start_hands_over_one(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="", end_event="ended", offer=NextEpisodeChoice.TIMEOUT)

    controller.start_playback(ctx)

    assert s.store.put_values == ["1:EP2"]


def test_continue_hands_over_nothing(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="2:EP1", end_event="ended", offer=NextEpisodeChoice.CONTINUE)

    controller.start_playback(ctx)

    assert s.store.put_values == []
    assert "put" not in s.events
    s.start.assert_called_once_with(ctx, s.episode)


def test_cancel_hands_over_nothing(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, end_event="ended", offer=NextEpisodeChoice.CANCEL)

    controller.start_playback(ctx)

    assert s.store.put_values == []
    s.start.assert_not_called()


def test_still_watching_continue_hands_over_nothing(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="3:EP1", limit=3, end_event="ended")

    controller.start_playback(ctx)

    s.ask.assert_called_once_with(ctx, s.episode)
    assert s.store.put_values == []
    s.start.assert_called_once_with(ctx, s.episode)


def test_timeout_without_valid_next_id_hands_over_nothing(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, next_id=None, end_event="ended", offer=NextEpisodeChoice.TIMEOUT)

    controller.start_playback(ctx)

    assert s.store.put_values == []
    s.start.assert_called_once_with(ctx, s.episode)


def test_put_failure_still_starts_next_episode(ctx, monkeypatch):
    s = _chain_setup(
        ctx, monkeypatch, put_error=RuntimeError("full"), end_event="ended", offer=NextEpisodeChoice.TIMEOUT
    )
    log_error = MagicMock()
    monkeypatch.setattr(controller, "log_error_with_trace", log_error)

    controller.start_playback(ctx)

    s.start.assert_called_once_with(ctx, s.episode)
    log_error.assert_not_called()


def test_disabled_feature_does_not_touch_chain_store(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, enabled=False, end_event="ended")

    controller.start_playback(ctx)

    s.store_class.assert_not_called()
    assert "take" not in s.events


def test_stop_consumes_handoff_but_writes_nothing(ctx, monkeypatch):
    s = _chain_setup(ctx, monkeypatch, stored="2:EP1", end_event="stopped")

    controller.start_playback(ctx)

    assert s.events.count("take") == 1
    assert s.store.put_values == []
    s.offer.assert_not_called()
    s.ask.assert_not_called()
