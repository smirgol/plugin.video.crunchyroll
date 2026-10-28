"""Tests for the auto-continue chain handoff."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from resources.lib.next_episode import chain
from resources.lib.next_episode.chain import (
    ChainHandoff,
    asks_presence,
    consume_streak,
    format_handoff,
    handoff_after,
    parse_handoff,
    publish_handoff,
    read_presence_limit,
    streak_for,
)
from resources.lib.next_episode.countdown import NextEpisodeChoice


class FakeStore:
    def __init__(self, value="", take_error=None, put_error=None):
        self.value, self.take_error, self.put_error = value, take_error, put_error
        self.put_values = []

    def take(self):
        if self.take_error is not None:
            raise self.take_error
        value, self.value = self.value, ""
        return value

    def put(self, value):
        if self.put_error is not None:
            raise self.put_error
        self.put_values.append(value)


class FakeWindow:
    def __init__(self, window_id):
        self.window_id = window_id
        self.properties = {}

    def getProperty(self, key):  # noqa: N802 - mirrors xbmcgui.Window
        return self.properties.get(key, "")

    def setProperty(self, key, value):  # noqa: N802
        self.properties[key] = value

    def clearProperty(self, key):  # noqa: N802
        self.properties.pop(key, None)


@pytest.fixture
def logs(monkeypatch):
    recorded = []
    monkeypatch.setattr(chain, "crunchy_log", lambda message, level=None: recorded.append((message, level)))
    return recorded


class TestParseHandoff:
    def test_parses_streak_and_id(self):
        assert parse_handoff("2:GG1UX5ZQX") == ChainHandoff(2, "GG1UX5ZQX")

    def test_id_may_contain_colon(self):
        assert parse_handoff("1:a:b") == ChainHandoff(1, "a:b")

    @pytest.mark.parametrize("value", ["", "2", "2:", ":X", "-1:X", "a:X", " 2:X", "²:X", None, 3, MagicMock()])
    def test_rejects_invalid(self, value):
        assert parse_handoff(value) is None

    def test_roundtrip(self):
        assert parse_handoff(format_handoff(ChainHandoff(3, "X1"))) == ChainHandoff(3, "X1")
        assert format_handoff(ChainHandoff(3, "X1")) == "3:X1"


class TestStreakFor:
    def test_matching_id_continues_streak(self):
        assert streak_for(ChainHandoff(2, "E1"), "E1") == 2

    def test_other_id_resets(self):
        assert streak_for(ChainHandoff(2, "E1"), "E2") == 0

    def test_no_handoff_resets(self):
        assert streak_for(None, "E1") == 0

    @pytest.mark.parametrize("current_id", [None, MagicMock()])
    def test_non_str_current_id_resets(self, current_id):
        assert streak_for(ChainHandoff(2, "E1"), current_id) == 0


class TestAsksPresence:
    @pytest.mark.parametrize(
        ("streak", "limit", "expected"),
        [
            (0, 3, False),
            (2, 3, False),
            (3, 3, True),
            (4, 3, True),
            (0, 0, False),
            (99, 0, False),
            (1, 1, True),
        ],
    )
    def test_asks_presence(self, streak, limit, expected):
        assert asks_presence(streak, limit) is expected


class TestHandoffAfter:
    def test_timeout_increments_streak(self):
        assert handoff_after(NextEpisodeChoice.TIMEOUT, 2, "E2") == ChainHandoff(3, "E2")

    def test_timeout_from_zero(self):
        assert handoff_after(NextEpisodeChoice.TIMEOUT, 0, "E2") == ChainHandoff(1, "E2")

    @pytest.mark.parametrize("choice", [NextEpisodeChoice.CONTINUE, NextEpisodeChoice.CANCEL])
    def test_user_choices_write_nothing(self, choice):
        assert handoff_after(choice, 2, "E2") is None

    @pytest.mark.parametrize("episode_id", [None, "", MagicMock()])
    def test_invalid_episode_id_writes_nothing(self, episode_id):
        assert handoff_after(NextEpisodeChoice.TIMEOUT, 2, episode_id) is None


class TestReadPresenceLimit:
    def test_reads_presence_setting(self):
        addon = MagicMock()
        addon.getSettingInt.return_value = 5

        assert read_presence_limit(addon) == 5
        addon.getSettingInt.assert_called_once_with("next_episode_still_watching_after")

    @pytest.mark.parametrize(
        ("stored", "expected"),
        [(0, 0), (10, 10), (11, 10), (-1, 0), ("7", 3), (True, 3)],
    )
    def test_clamps_and_falls_back(self, stored, expected):
        addon = MagicMock()
        addon.getSettingInt.return_value = stored

        assert read_presence_limit(addon) == expected

    def test_exception_falls_back_to_three(self):
        addon = MagicMock()
        addon.getSettingInt.side_effect = RuntimeError

        assert read_presence_limit(addon) == 3


class TestConsumeStreak:
    def test_matching_handoff_returns_streak_and_logs(self, logs):
        assert consume_streak(FakeStore("2:E1"), "E1") == 2
        assert logs == [("next episode chain: handoff matched, streak 2", chain.xbmc.LOGINFO)]

    def test_take_clears_store(self, logs):
        store = FakeStore("2:E1")

        consume_streak(store, "E1")

        assert store.value == ""

    def test_empty_store_logs_no_handoff(self, logs):
        assert consume_streak(FakeStore(""), "E1") == 0
        assert logs == [("next episode chain: no handoff", chain.xbmc.LOGINFO)]

    def test_other_episode_logs_reset(self, logs):
        assert consume_streak(FakeStore("2:E1"), "E9") == 0
        assert logs == [("next episode chain: no handoff (other episode)", chain.xbmc.LOGINFO)]

    def test_unreadable_value_counts_as_no_handoff(self, logs):
        store = MagicMock()
        store.take.return_value = MagicMock()

        assert consume_streak(store, "E1") == 0
        assert [message for message, _ in logs] == ["next episode chain: no handoff"]

    def test_take_failure_counts_as_no_handoff(self, logs):
        store = FakeStore(take_error=RuntimeError("boom"))

        assert consume_streak(store, "E1") == 0
        assert [message for message, _ in logs] == ["next episode chain: no handoff"]


class TestPublishHandoff:
    def test_publish_writes_formatted_value(self, logs):
        store = FakeStore()

        publish_handoff(store, ChainHandoff(3, "E2"))

        assert store.put_values == ["3:E2"]
        assert logs == []

    def test_publish_failure_logs_warning_and_does_not_raise(self, logs):
        store = FakeStore(put_error=RuntimeError("boom"))

        publish_handoff(store, ChainHandoff(3, "E2"))

        assert logs == [("next episode chain: could not store handoff", chain.xbmc.LOGWARNING)]


class TestHomeWindowChainStore:
    @pytest.fixture
    def windows(self, monkeypatch):
        created = {}
        monkeypatch.setattr(
            chain,
            "xbmcgui",
            SimpleNamespace(Window=lambda window_id: created.setdefault(window_id, FakeWindow(window_id))),
        )
        return created

    def test_uses_home_window(self, windows):
        chain.HomeWindowChainStore()

        assert list(windows) == [10000]

    def test_put_then_take_returns_value_and_clears(self, windows):
        store = chain.HomeWindowChainStore()

        store.put("2:E1")

        assert windows[10000].properties == {"plugin.video.crunchyroll.next_episode.chain": "2:E1"}
        assert store.take() == "2:E1"
        assert windows[10000].properties == {}
        assert store.take() == ""

    def test_value_survives_new_store_instance(self, windows):
        chain.HomeWindowChainStore().put("1:E1")

        assert chain.HomeWindowChainStore().take() == "1:E1"
