from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PRODUCTION_API = "https://external-api.kalshi.com/trade-api/v2"
DEMO_API = "https://external-api.demo.kalshi.co/trade-api/v2"
ODDS_API = "https://api.the-odds-api.com/v4"

# v1 is MLB moneyline only (KXMLBGAME). Other sports can be added later.
LEAGUES: dict[str, dict[str, str]] = {
    "mlb": {"series": "KXMLBGAME", "label": "MLB", "sport": "baseball_mlb"},
}

DEFAULT_LEAGUES = ("mlb",)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("SPORTSBOT_DATA_DIR", "data")))
    leagues: tuple[str, ...] = DEFAULT_LEAGUES
    bankroll: float = field(default_factory=lambda: _float_env("SPORTSBOT_BANKROLL", 1000.0))
    max_trade_usd: float = field(default_factory=lambda: _float_env("SPORTSBOT_MAX_TRADE_USD", 25.0))
    max_daily_usd: float = field(default_factory=lambda: _float_env("SPORTSBOT_MAX_DAILY_USD", 200.0))
    max_open_positions: int = field(default_factory=lambda: _int_env("SPORTSBOT_MAX_OPEN_POSITIONS", 8))
    min_edge: float = field(default_factory=lambda: _float_env("SPORTSBOT_MIN_EDGE", 0.02))
    min_volume: float = field(default_factory=lambda: _float_env("SPORTSBOT_MIN_VOLUME", 50.0))
    wide_spread: float = field(default_factory=lambda: _float_env("SPORTSBOT_WIDE_SPREAD", 0.08))
    kalshi_market_url: str = PRODUCTION_API
    kalshi_trade_url: str = field(
        default_factory=lambda: DEMO_API if os.getenv("KALSHI_ENV", "demo") != "prod" else PRODUCTION_API
    )
    kalshi_api_key_id: str = field(default_factory=lambda: os.getenv("KALSHI_API_KEY_ID", ""))
    kalshi_private_key_path: str = field(default_factory=lambda: os.getenv("KALSHI_PRIVATE_KEY_PATH", ""))
    live_enabled: bool = field(default_factory=lambda: _bool_env("KALSHI_ENABLE_LIVE"))
    odds_api_key: str = field(default_factory=lambda: os.getenv("ODDS_API_KEY", ""))
    request_timeout: float = 20.0

    def resolved_leagues(self, requested: list[str] | None) -> list[str]:
        if not requested:
            return list(self.leagues)
        unknown = [league for league in requested if league not in LEAGUES]
        if unknown:
            raise ValueError(f"Unknown league(s): {', '.join(unknown)}. Choose from {', '.join(LEAGUES)}")
        return requested

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sportsbot.db"

    @property
    def kill_switch_path(self) -> Path:
        return self.data_dir / "KILL"

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir
