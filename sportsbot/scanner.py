from __future__ import annotations

from sportsbot.config import LEAGUES, Settings
from sportsbot.kalshi.client import KalshiClient
from sportsbot.kalshi.models import EventMarkets, GameMarket


def _active_markets(event: dict) -> list[dict]:
    markets = event.get("markets") or []
    return [market for market in markets if market.get("status") in {"active", "open"}]


def event_from_api(event: dict, league: str) -> EventMarkets | None:
    meta = LEAGUES[league]
    markets = [
        GameMarket.from_api(market, event, league, meta["label"]) for market in _active_markets(event)
    ]
    if not markets:
        return None
    occurrence = next((market.occurrence for market in markets if market.occurrence), None)
    return EventMarkets(
        event_ticker=event.get("event_ticker", ""),
        series_ticker=event.get("series_ticker", ""),
        title=event.get("title") or "",
        subtitle=event.get("sub_title") or "",
        league=league,
        league_label=meta["label"],
        mutually_exclusive=bool(event.get("mutually_exclusive")),
        occurrence=occurrence,
        markets=markets,
    )


class MarketScanner:
    def __init__(self, settings: Settings, client: KalshiClient | None = None) -> None:
        self.settings = settings
        self.client = client or KalshiClient(settings.kalshi_market_url, timeout=settings.request_timeout)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def scan_league(self, league: str) -> list[EventMarkets]:
        if league not in LEAGUES:
            raise ValueError(f"Unknown league: {league}")
        series = LEAGUES[league]["series"]
        raw_events = self.client.list_events(series_ticker=series, status="open")
        events = [event_from_api(event, league) for event in raw_events]
        present = [event for event in events if event is not None]
        present.sort(key=lambda event: (event.kickoff is None, event.kickoff))
        return present

    def scan(self, leagues: list[str] | None = None) -> list[EventMarkets]:
        chosen = self.settings.resolved_leagues(leagues)
        board: list[EventMarkets] = []
        for league in chosen:
            board.extend(self.scan_league(league))
        board.sort(key=lambda event: (event.league, event.kickoff is None, event.kickoff))
        return board
