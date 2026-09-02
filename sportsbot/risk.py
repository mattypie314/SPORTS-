from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sportsbot.config import Settings


class RiskBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class RiskSnapshot:
    bankroll: float
    open_positions: int
    spent_today: float
    remaining_daily: float
    kill_switch: bool


class RiskManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def kill_switch_on(self) -> bool:
        return Path(self.settings.kill_switch_path).exists()

    def check_entry(self, *, notional: float, open_positions: int, spent_today: float) -> None:
        if self.kill_switch_on():
            raise RiskBlocked(f"Kill switch is on ({self.settings.kill_switch_path})")
        if notional <= 0:
            raise RiskBlocked("Trade size must be positive")
        if notional > self.settings.max_trade_usd + 1e-9:
            raise RiskBlocked(
                f"Trade ${notional:.2f} exceeds max per trade ${self.settings.max_trade_usd:.2f}"
            )
        if spent_today + notional > self.settings.max_daily_usd + 1e-9:
            raise RiskBlocked(
                f"Trade would push daily spend to ${spent_today + notional:.2f} "
                f"(cap ${self.settings.max_daily_usd:.2f})"
            )
        if open_positions >= self.settings.max_open_positions:
            raise RiskBlocked(
                f"Already at max open positions ({self.settings.max_open_positions})"
            )

    def size_for_price(self, price: float) -> float:
        if price <= 0 or price >= 1:
            return 0.0
        contracts = self.settings.max_trade_usd / price
        return max(round(contracts, 2), 0.01)

    def snapshot(self, *, cash: float, open_positions: int, spent_today: float) -> RiskSnapshot:
        return RiskSnapshot(
            bankroll=cash,
            open_positions=open_positions,
            spent_today=spent_today,
            remaining_daily=max(self.settings.max_daily_usd - spent_today, 0.0),
            kill_switch=self.kill_switch_on(),
        )


def today_utc() -> str:
    return date.today().isoformat()
