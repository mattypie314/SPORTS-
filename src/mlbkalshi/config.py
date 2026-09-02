from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def default_bankroll() -> float:
    if _bool("SMALL_BANKROLL"):
        return 35.0
    raw = os.getenv("BANKROLL") or os.getenv("SPORTSBOT_BANKROLL")
    if raw:
        return float(raw)
    return 100.0


@dataclass(frozen=True)
class Settings:
    bankroll: float
    odds_api_key: str
    live_trading: bool
    kalshi_key_id: str
    kalshi_private_key_path: str
    books_path: str
    data_dir: str
    kalshi_env: str

    @classmethod
    def from_env(cls, bankroll: float | None = None) -> Settings:
        return cls(
            bankroll=bankroll if bankroll is not None else default_bankroll(),
            odds_api_key=os.getenv("ODDS_API_KEY", ""),
            live_trading=_bool("LIVE_TRADING"),
            kalshi_key_id=os.getenv("KALSHI_API_KEY_ID", ""),
            kalshi_private_key_path=os.getenv("KALSHI_PRIVATE_KEY_PATH", ""),
            books_path=os.getenv("BOOK_LINES_PATH", ""),
            data_dir=os.getenv("MLBKALSHI_DATA", "data"),
            kalshi_env=os.getenv("KALSHI_ENV", "demo"),
        )

    @property
    def has_keys(self) -> bool:
        return bool(self.kalshi_key_id and self.kalshi_private_key_path)

    @property
    def live_allowed(self) -> bool:
        return self.live_trading and self.has_keys
