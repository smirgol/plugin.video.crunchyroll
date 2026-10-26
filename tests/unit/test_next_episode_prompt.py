"""Tests for should_offer_next_episode."""

from unittest.mock import MagicMock

import pytest

from resources.lib.models.content import EpisodeData
from resources.lib.next_episode.prompt import should_offer_next_episode


@pytest.mark.parametrize("ended_regularly", [True, False])
@pytest.mark.parametrize("abort_requested", [True, False])
@pytest.mark.parametrize("has_next_episode", [True, False])
def test_should_offer_next_episode_table(ended_regularly, abort_requested, has_next_episode):
    next_episode = MagicMock(spec=EpisodeData) if has_next_episode else None

    expected = ended_regularly and not abort_requested and has_next_episode

    assert should_offer_next_episode(ended_regularly, abort_requested, next_episode) is expected
