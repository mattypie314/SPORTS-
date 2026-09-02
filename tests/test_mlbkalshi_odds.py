import pytest

from mlbkalshi.odds import american_to_implied, implied_to_american, no_vig, no_vig_two_way, remove_vig


def test_american_to_implied():
    assert american_to_implied(-100) == pytest.approx(0.5)
    assert american_to_implied(100) == pytest.approx(0.5)
    assert american_to_implied(-150) == pytest.approx(0.6)
    assert american_to_implied(150) == pytest.approx(100 / 250)


def test_implied_roundtrip():
    assert implied_to_american(0.6) == -150
    assert implied_to_american(american_to_implied(130)) == 130


def test_two_way_no_vig_sums_to_one():
    a, b = no_vig_two_way(-150, 130)
    assert a + b == pytest.approx(1.0)
    assert a > b


def test_multi_way_no_vig():
    fair = no_vig([-120, 250, 400])
    assert sum(fair) == pytest.approx(1.0)
    assert fair[0] == max(fair)


def test_remove_vig_rejects_empty():
    with pytest.raises(ValueError):
        remove_vig([])
