import pytest

from mlbkalshi.fees import (
    TAKER_RATE,
    evaluate,
    fee_per_contract,
    kelly_full,
    net_ev,
    size_trade,
)


def test_taker_fee_matches_spec():
    # 0.07 * 0.50 * 0.50 = 0.0175
    assert fee_per_contract(0.50) == pytest.approx(TAKER_RATE * 0.25)
    assert fee_per_contract(0.50, maker=True) == pytest.approx(0.0175 * 0.25)


def test_net_ev_subtracts_fee():
    assert net_ev(0.62, 0.55) == pytest.approx(0.62 - 0.55 - fee_per_contract(0.55))


def test_kelly_and_risk_cap():
    full = kelly_full(0.64, 0.55)
    assert full == pytest.approx((0.64 - 0.55) / 0.45)
    sized = size_trade(0.64, 0.55, bankroll=100, kelly_fraction=0.30, risk_cap=0.06)
    assert sized.risk <= 6.0 + 1e-9
    assert sized.kelly_used == pytest.approx(0.30)
    assert sized.contracts == pytest.approx(round(sized.risk / 0.55, 2))


def test_pass_at_six_percent():
    # fair 0.64, ask 0.55, fee ≈ 0.0173 → net ≈ 0.0727
    result = evaluate(fair=0.64, kalshi_yes=0.55, side="yes", bankroll=100)
    assert result.passed
    assert result.verdict == "PASS"
    assert result.net_ev >= 0.06


def test_fail_below_gate():
    result = evaluate(fair=0.57, kalshi_yes=0.55, side="yes", bankroll=100)
    assert not result.passed
    assert "6%" in result.reason


def test_tight_books_four_percent_floor():
    # fair 0.60, ask 0.54, fee ≈ 0.0174 → net ≈ 0.0426
    result = evaluate(
        fair=0.60,
        kalshi_yes=0.54,
        side="yes",
        bankroll=100,
        spread=0.01,
        disagree_pts=1.0,
    )
    assert result.passed
    assert "4%" in result.reason


def test_book_disagreement_raises_gate():
    result = evaluate(
        fair=0.64,
        kalshi_yes=0.55,
        side="yes",
        bankroll=100,
        disagree_pts=5.0,
    )
    # net ≈ 0.073 < 0.08
    assert not result.passed
    assert "8%" in result.reason


def test_skip_heavy_favorite_without_ten():
    result = evaluate(fair=0.86, kalshi_yes=0.82, side="yes", bankroll=100)
    assert not result.passed
    assert "80¢" in result.reason or "favorite" in result.reason


def test_low_confidence_extreme_price_always_fails():
    result = evaluate(
        fair=0.55,
        kalshi_yes=0.02,
        side="yes",
        bankroll=100,
        low_confidence=True,
        source_of_fair="model_fair",
    )
    assert not result.passed
    assert "15¢" in result.reason or "80¢" in result.reason


def test_low_confidence_needs_ten():
    result = evaluate(
        fair=0.64,
        kalshi_yes=0.55,
        side="yes",
        bankroll=100,
        low_confidence=True,
        source_of_fair="model_fair",
    )
    assert not result.passed
    assert "low_confidence" in result.reason


def test_yes_no_side_flips_price():
    yes = evaluate(fair=0.64, kalshi_yes=0.55, side="yes", bankroll=100)
    no = evaluate(fair=0.64, kalshi_yes=0.55, side="no", bankroll=100)
    assert no.price == pytest.approx(0.45)
    assert no.fair == pytest.approx(0.36)
    assert yes.price == pytest.approx(0.55)
