from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sportsbot.config import Settings
from sportsbot.kalshi.models import EventMarkets
from sportsbot.risk import RiskBlocked, RiskManager, today_utc
from sportsbot.signals import Signal


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PaperFill:
    fill_id: str
    created_at: str
    signal_kind: str
    event_ticker: str
    ticker: str
    side: str
    price: float
    contracts: float
    notional: float
    note: str

    def to_dict(self) -> dict:
        return {
            "fill_id": self.fill_id,
            "created_at": self.created_at,
            "signal_kind": self.signal_kind,
            "event_ticker": self.event_ticker,
            "ticker": self.ticker,
            "side": self.side,
            "price": self.price,
            "contracts": self.contracts,
            "notional": self.notional,
            "note": self.note,
        }


class PaperBook:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.ensure_data_dir()
        self.path = Path(settings.db_path)
        self.risk = RiskManager(settings)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fills (
                    fill_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    day TEXT NOT NULL,
                    signal_kind TEXT NOT NULL,
                    event_ticker TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    contracts REAL NOT NULL,
                    notional REAL NOT NULL,
                    note TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS account (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            existing = conn.execute("SELECT value FROM account WHERE key = 'cash'").fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO account(key, value) VALUES ('cash', ?)",
                    (str(self.settings.bankroll),),
                )

    def cash(self) -> float:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM account WHERE key = 'cash'").fetchone()
        return float(row["value"]) if row else self.settings.bankroll

    def fills(self) -> list[PaperFill]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM fills ORDER BY created_at DESC").fetchall()
        return [self._row_to_fill(row) for row in rows]

    def open_position_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(DISTINCT event_ticker) AS n FROM fills").fetchone()
        return int(row["n"]) if row else 0

    def spent_today(self) -> float:
        day = today_utc()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(notional), 0) AS n FROM fills WHERE day = ? AND side = 'bid'",
                (day,),
            ).fetchone()
        return float(row["n"]) if row else 0.0

    def status(self) -> dict:
        snapshot = self.risk.snapshot(
            cash=self.cash(),
            open_positions=self.open_position_count(),
            spent_today=self.spent_today(),
        )
        return {
            "mode": "paper",
            "cash": round(snapshot.bankroll, 2),
            "starting_bankroll": self.settings.bankroll,
            "open_positions": snapshot.open_positions,
            "spent_today": round(snapshot.spent_today, 2),
            "remaining_daily": round(snapshot.remaining_daily, 2),
            "kill_switch": snapshot.kill_switch,
            "fills": [fill.to_dict() for fill in self.fills()],
        }

    def execute_signal(self, signal: Signal, events: list[EventMarkets]) -> list[PaperFill]:
        if signal.kind not in {"arb_buy", "arb_sell", "sportsbook_value"}:
            return []
        event = next((item for item in events if item.event_ticker == signal.event_ticker), None)
        if event is None:
            return []
        markets = {market.ticker: market for market in event.markets}
        fills: list[PaperFill] = []
        planned: list[tuple[str, str, float, float, float]] = []

        if signal.kind == "arb_buy":
            prices = []
            for ticker in signal.tickers:
                market = markets[ticker]
                if market.yes_ask is None:
                    return []
                prices.append((ticker, market.yes_ask))
            basket = sum(price for _, price in prices)
            contracts = self.risk.size_for_price(basket)
            for ticker, price in prices:
                planned.append((ticker, "bid", price, contracts, round(contracts * price, 2)))
        elif signal.kind == "arb_sell":
            prices = []
            for ticker in signal.tickers:
                market = markets[ticker]
                if market.yes_bid is None:
                    return []
                prices.append((ticker, market.yes_bid))
            basket = sum(price for _, price in prices)
            contracts = self.risk.size_for_price(basket)
            for ticker, price in prices:
                planned.append((ticker, "ask", price, contracts, round(contracts * price, 2)))
        else:
            ticker = signal.tickers[0]
            market = markets[ticker]
            price = float(signal.details.get("price") or market.yes_ask or 0)
            if price <= 0:
                return []
            contracts = self.risk.size_for_price(price)
            notional = round(contracts * price, 2)
            planned.append((ticker, "bid", price, contracts, notional))

        total_notional = sum(item[4] for item in planned)
        try:
            self.risk.check_entry(
                notional=total_notional,
                open_positions=self.open_position_count(),
                spent_today=self.spent_today(),
            )
        except RiskBlocked:
            return []

        cash = self.cash()
        debit = total_notional if signal.kind != "arb_sell" else 0.0
        credit = total_notional if signal.kind == "arb_sell" else 0.0
        if cash - debit + credit < 0:
            return []

        with self._connect() as conn:
            for ticker, side, price, contracts, notional in planned:
                fill = PaperFill(
                    fill_id=str(uuid.uuid4()),
                    created_at=_utc_now(),
                    signal_kind=signal.kind,
                    event_ticker=signal.event_ticker,
                    ticker=ticker,
                    side=side,
                    price=price,
                    contracts=contracts,
                    notional=notional,
                    note=signal.summary,
                )
                conn.execute(
                    """
                    INSERT INTO fills(
                        fill_id, created_at, day, signal_kind, event_ticker, ticker,
                        side, price, contracts, notional, note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fill.fill_id,
                        fill.created_at,
                        today_utc(),
                        fill.signal_kind,
                        fill.event_ticker,
                        fill.ticker,
                        fill.side,
                        fill.price,
                        fill.contracts,
                        fill.notional,
                        fill.note,
                    ),
                )
                fills.append(fill)
            new_cash = cash - debit + credit
            conn.execute("UPDATE account SET value = ? WHERE key = 'cash'", (str(round(new_cash, 2)),))
        return fills

    def execute_actionable(self, signals: list[Signal], events: list[EventMarkets]) -> list[PaperFill]:
        fills: list[PaperFill] = []
        for signal in signals:
            fills.extend(self.execute_signal(signal, events))
        return fills

    @staticmethod
    def _row_to_fill(row: sqlite3.Row) -> PaperFill:
        return PaperFill(
            fill_id=row["fill_id"],
            created_at=row["created_at"],
            signal_kind=row["signal_kind"],
            event_ticker=row["event_ticker"],
            ticker=row["ticker"],
            side=row["side"],
            price=row["price"],
            contracts=row["contracts"],
            notional=row["notional"],
            note=row["note"],
        )


def dump_status(status: dict) -> str:
    return json.dumps(status, indent=2)
