from datetime import datetime, timezone

from sportsbot.kalshi.models import EventMarkets, GameMarket
from sportsbot.signals import collect_signals, complementary_buy_arb, complementary_sell_arb


def market(team: str, bid: float, ask: float, ticker: str, volume: float = 200) -> GameMarket:
    return GameMarket(
        ticker=ticker,
        event_ticker="EVT",
        series_ticker="KXMLBGAME",
        event_title="A vs B",
        event_subtitle="A vs B",
        league="mlb",
        league_label="MLB",
        team=team,
        title=f"{team} wins",
        status="active",
        yes_bid=bid,
        yes_ask=ask,
        no_bid=round(1 - ask, 4),
        no_ask=round(1 - bid, 4),
        last_price=ask,
        previous_price=ask - 0.05,
        volume=volume,
        open_interest=10,
        close_time=datetime(2026, 9, 9, tzinfo=timezone.utc),
        occurrence=datetime(2026, 9, 9, tzinfo=timezone.utc),
        mutually_exclusive=True,
    )


def event(markets: list[GameMarket]) -> EventMarkets:
    return EventMarkets(
        event_ticker="EVT",
        series_ticker="KXMLBGAME",
        title="A vs B",
        subtitle="A vs B",
        league="mlb",
        league_label="MLB",
        mutually_exclusive=True,
        occurrence=datetime(2026, 9, 9, tzinfo=timezone.utc),
        markets=markets,
    )


def test_buy_arb_when_asks_sum_under_one():
    game = event([market("A", 0.40, 0.41, "A"), market("B", 0.55, 0.56, "B")])
    signal = complementary_buy_arb(game, min_edge=0.02, min_volume=50)
    assert signal is not None
    assert signal.kind == "arb_buy"
    assert round(signal.edge, 2) == 0.03


def test_no_buy_arb_when_edge_too_small():
    game = event([market("A", 0.48, 0.49, "A"), market("B", 0.50, 0.51, "B")])
    assert complementary_buy_arb(game, min_edge=0.02, min_volume=50) is None


def test_sell_arb_when_bids_sum_over_one():
    game = event([market("A", 0.52, 0.53, "A"), market("B", 0.51, 0.52, "B")])
    signal = complementary_sell_arb(game, min_edge=0.02, min_volume=50)
    assert signal is not None
    assert signal.kind == "arb_sell"
    assert round(signal.edge, 2) == 0.03


def test_collect_includes_wide_spread_and_move():
    game = event([market("A", 0.30, 0.45, "A"), market("B", 0.50, 0.52, "B")])
    signals = collect_signals([game], min_edge=0.20, min_volume=50, wide_spread=0.08)
    kinds = {signal.kind for signal in signals}
    assert "wide_spread" in kinds
    assert "price_move" in kinds


def test_move_ignores_zero_previous_print():
    from sportsbot.signals import move_signal

    stale = market("A", 0.30, 0.45, "A")
    stale = GameMarket(**{**stale.__dict__, "previous_price": 0.0, "last_price": 0.45})
    game = event([stale])
    assert move_signal(stale, game) is None
