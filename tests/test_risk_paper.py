from datetime import datetime, timezone
from pathlib import Path

import pytest

from sportsbot.config import Settings
from sportsbot.kalshi.models import EventMarkets, GameMarket
from sportsbot.paper import PaperBook
from sportsbot.risk import RiskBlocked, RiskManager
from sportsbot.signals import complementary_buy_arb


def settings(tmp_path: Path, **overrides) -> Settings:
    values = dict(
        data_dir=tmp_path,
        bankroll=1000,
        max_trade_usd=25,
        max_daily_usd=200,
        max_open_positions=8,
        min_edge=0.02,
        min_volume=0,
    )
    values.update(overrides)
    return Settings(**values)


def arb_event() -> EventMarkets:
    def mkt(team: str, bid: float, ask: float) -> GameMarket:
        return GameMarket(
            ticker=team,
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
            no_bid=None,
            no_ask=None,
            last_price=ask,
            previous_price=ask,
            volume=100,
            open_interest=10,
            close_time=datetime(2026, 9, 9, tzinfo=timezone.utc),
            occurrence=datetime(2026, 9, 9, tzinfo=timezone.utc),
            mutually_exclusive=True,
        )

    return EventMarkets(
        event_ticker="EVT",
        series_ticker="KXMLBGAME",
        title="A vs B",
        subtitle="A vs B",
        league="mlb",
        league_label="MLB",
        mutually_exclusive=True,
        occurrence=datetime(2026, 9, 9, tzinfo=timezone.utc),
        markets=[mkt("A", 0.40, 0.41), mkt("B", 0.55, 0.56)],
    )


def test_risk_blocks_oversize_and_kill_switch(tmp_path: Path):
    mgr = RiskManager(settings(tmp_path, max_trade_usd=10))
    with pytest.raises(RiskBlocked):
        mgr.check_entry(notional=25, open_positions=0, spent_today=0)
    (tmp_path / "KILL").write_text("stop")
    with pytest.raises(RiskBlocked):
        mgr.check_entry(notional=5, open_positions=0, spent_today=0)


def test_paper_book_executes_buy_arb(tmp_path: Path):
    book = PaperBook(settings(tmp_path))
    event = arb_event()
    signal = complementary_buy_arb(event, min_edge=0.02, min_volume=0)
    fills = book.execute_signal(signal, [event])
    assert len(fills) == 2
    assert all(fill.side == "bid" for fill in fills)
    status = book.status()
    assert status["open_positions"] == 1
    assert status["cash"] < 1000
    assert len(status["fills"]) == 2


def test_paper_ignores_wide_spread(tmp_path: Path):
    book = PaperBook(settings(tmp_path))
    event = arb_event()
    from sportsbot.signals import Signal

    signal = Signal(
        kind="wide_spread",
        league="mlb",
        league_label="MLB",
        event_ticker="EVT",
        title="A vs B",
        subtitle="A",
        edge=0.1,
        summary="wide",
        tickers=["A"],
    )
    assert book.execute_signal(signal, [event]) == []
