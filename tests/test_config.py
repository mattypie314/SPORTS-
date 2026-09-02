import pytest

from sportsbot.config import DEFAULT_LEAGUES, LEAGUES, Settings


def test_only_mlb_is_enabled():
    assert list(LEAGUES) == ["mlb"]
    assert DEFAULT_LEAGUES == ("mlb",)
    assert Settings().resolved_leagues(None) == ["mlb"]


def test_unknown_league_rejected():
    with pytest.raises(ValueError, match="nfl"):
        Settings().resolved_leagues(["nfl"])
