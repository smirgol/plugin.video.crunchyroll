"""Tests for read_clamped_int."""

from unittest.mock import MagicMock

import pytest

from resources.lib.next_episode.settings import read_clamped_int

SETTING_ID = "some_setting"
DEFAULT = 3
MINIMUM = 0
MAXIMUM = 10


def _read(addon):
    return read_clamped_int(addon, SETTING_ID, DEFAULT, MINIMUM, MAXIMUM)


class TestReadClampedInt:
    @pytest.mark.parametrize(("stored", "expected"), [(3, 3), (0, 0), (10, 10), (7, 7)])
    def test_returns_value_within_bounds(self, stored, expected):
        addon = MagicMock()
        addon.getSettingInt.return_value = stored

        assert _read(addon) == expected

    @pytest.mark.parametrize(("stored", "expected"), [(-1, 0), (11, 10), (999, 10)])
    def test_clamps_out_of_range(self, stored, expected):
        addon = MagicMock()
        addon.getSettingInt.return_value = stored

        assert _read(addon) == expected

    def test_falls_back_on_exception(self):
        addon = MagicMock()
        addon.getSettingInt.side_effect = RuntimeError("no setting")

        assert _read(addon) == DEFAULT
        addon.getSettingInt.assert_called_once_with(SETTING_ID)

    @pytest.mark.parametrize("stored", ["5", True, None, 2.5])
    def test_falls_back_on_non_int(self, stored):
        addon = MagicMock()
        addon.getSettingInt.return_value = stored

        assert _read(addon) == DEFAULT

    def test_reads_given_setting_id(self):
        addon = MagicMock()
        addon.getSettingInt.return_value = 4

        _read(addon)

        addon.getSettingInt.assert_called_once_with(SETTING_ID)
