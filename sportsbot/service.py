from __future__ import annotations

from sportsbot.config import Settings
from sportsbot.kalshi.models import EventMarkets
from sportsbot.odds import OddsClient, sportsbook_signals
from sportsbot.scanner import MarketScanner
from sportsbot.signals import Signal, collect_signals


def scan_board(settings: Settings, leagues: list[str] | None = None) -> tuple[list[EventMarkets], list[Signal]]:
    scanner = MarketScanner(settings)
    try:
        events = scanner.scan(leagues)
    finally:
        scanner.close()
    extra: list[Signal] = []
    if settings.odds_api_key:
        odds = OddsClient(settings)
        try:
            quotes = {league: odds.fetch_league(league) for league in {event.league for event in events}}
        finally:
            odds.close()
        extra = sportsbook_signals(events, quotes, settings.min_edge)
    signals = collect_signals(
        events,
        min_edge=settings.min_edge,
        min_volume=settings.min_volume,
        wide_spread=settings.wide_spread,
        extra=extra,
    )
    return events, signals


def serialize_board(events: list[EventMarkets], signals: list[Signal]) -> dict:
    return {
        "events": [event.to_dict() for event in events],
        "signals": [signal.to_dict() for signal in signals],
    }
