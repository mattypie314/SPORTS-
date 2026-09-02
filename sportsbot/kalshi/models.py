from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def parse_dollars(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_count(value: object) -> float:
    parsed = parse_dollars(value)
    return 0.0 if parsed is None else parsed


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def implied_to_american(probability: float) -> int | None:
    if probability <= 0 or probability >= 1:
        return None
    if probability >= 0.5:
        return int(round(-100 * probability / (1 - probability)))
    return int(round(100 * (1 - probability) / probability))


def format_american(odds: int | None) -> str:
    if odds is None:
        return "—"
    return f"+{odds}" if odds > 0 else str(odds)


@dataclass(frozen=True)
class GameMarket:
    ticker: str
    event_ticker: str
    series_ticker: str
    event_title: str
    event_subtitle: str
    league: str
    league_label: str
    team: str
    title: str
    status: str
    yes_bid: float | None
    yes_ask: float | None
    no_bid: float | None
    no_ask: float | None
    last_price: float | None
    previous_price: float | None
    volume: float
    open_interest: float
    close_time: datetime | None
    occurrence: datetime | None
    mutually_exclusive: bool
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def mid(self) -> float | None:
        if self.yes_bid is None or self.yes_ask is None:
            return None
        return round((self.yes_bid + self.yes_ask) / 2, 4)

    @property
    def spread(self) -> float | None:
        if self.yes_bid is None or self.yes_ask is None:
            return None
        return round(self.yes_ask - self.yes_bid, 4)

    @property
    def implied(self) -> float | None:
        return self.mid if self.mid is not None else self.last_price

    @property
    def american(self) -> int | None:
        if self.implied is None:
            return None
        return implied_to_american(self.implied)

    @classmethod
    def from_api(
        cls,
        market: dict,
        event: dict,
        league: str,
        league_label: str,
    ) -> GameMarket:
        team = (
            market.get("yes_sub_title")
            or market.get("subtitle")
            or market.get("title")
            or "Unknown"
        )
        return cls(
            ticker=market["ticker"],
            event_ticker=event.get("event_ticker") or market.get("event_ticker", ""),
            series_ticker=event.get("series_ticker", ""),
            event_title=event.get("title") or market.get("title") or "",
            event_subtitle=event.get("sub_title") or "",
            league=league,
            league_label=league_label,
            team=str(team),
            title=market.get("title") or "",
            status=market.get("status") or "",
            yes_bid=parse_dollars(market.get("yes_bid_dollars")),
            yes_ask=parse_dollars(market.get("yes_ask_dollars")),
            no_bid=parse_dollars(market.get("no_bid_dollars")),
            no_ask=parse_dollars(market.get("no_ask_dollars")),
            last_price=parse_dollars(market.get("last_price_dollars")),
            previous_price=parse_dollars(market.get("previous_price_dollars")),
            volume=parse_count(market.get("volume_fp")),
            open_interest=parse_count(market.get("open_interest_fp")),
            close_time=parse_iso(market.get("close_time")),
            occurrence=parse_iso(market.get("occurrence_datetime")),
            mutually_exclusive=bool(event.get("mutually_exclusive")),
            raw=market,
        )

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "event_ticker": self.event_ticker,
            "series_ticker": self.series_ticker,
            "event_title": self.event_title,
            "event_subtitle": self.event_subtitle,
            "league": self.league,
            "league_label": self.league_label,
            "team": self.team,
            "title": self.title,
            "status": self.status,
            "yes_bid": self.yes_bid,
            "yes_ask": self.yes_ask,
            "no_bid": self.no_bid,
            "no_ask": self.no_ask,
            "last_price": self.last_price,
            "previous_price": self.previous_price,
            "mid": self.mid,
            "spread": self.spread,
            "implied": self.implied,
            "american": self.american,
            "american_display": format_american(self.american),
            "volume": self.volume,
            "open_interest": self.open_interest,
            "close_time": self.close_time.isoformat() if self.close_time else None,
            "occurrence": self.occurrence.isoformat() if self.occurrence else None,
            "mutually_exclusive": self.mutually_exclusive,
        }


@dataclass
class EventMarkets:
    event_ticker: str
    series_ticker: str
    title: str
    subtitle: str
    league: str
    league_label: str
    mutually_exclusive: bool
    occurrence: datetime | None
    markets: list[GameMarket]

    @property
    def kickoff(self) -> datetime | None:
        if self.occurrence:
            return self.occurrence
        times = [market.occurrence or market.close_time for market in self.markets]
        present = [time for time in times if time is not None]
        return min(present) if present else None

    def to_dict(self) -> dict:
        return {
            "event_ticker": self.event_ticker,
            "series_ticker": self.series_ticker,
            "title": self.title,
            "subtitle": self.subtitle,
            "league": self.league,
            "league_label": self.league_label,
            "mutually_exclusive": self.mutually_exclusive,
            "kickoff": self.kickoff.isoformat() if self.kickoff else None,
            "markets": [market.to_dict() for market in self.markets],
        }
