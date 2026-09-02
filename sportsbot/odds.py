from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from sportsbot.config import LEAGUES, ODDS_API, Settings
from sportsbot.kalshi.models import EventMarkets
from sportsbot.signals import Signal, sportsbook_value_signal


def normalize_name(name: str) -> str:
    text = name.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(r"\b(the|fc|cf|sc|united|city|town)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def names_match(left: str, right: str) -> bool:
    a = normalize_name(left)
    b = normalize_name(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if a in b or b in a:
        return True
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    if not a_tokens or not b_tokens:
        return False
    overlap = a_tokens & b_tokens
    return len(overlap) >= 1 and (len(overlap) / min(len(a_tokens), len(b_tokens))) >= 0.5


def american_to_prob(odds: int) -> float:
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def devig(probabilities: list[float]) -> list[float]:
    total = sum(probabilities)
    if total <= 0:
        return probabilities
    return [prob / total for prob in probabilities]


@dataclass(frozen=True)
class BookQuote:
    sport: str
    home: str
    away: str
    home_prob: float
    away_prob: float


class OddsClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=settings.request_timeout)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def fetch_league(self, league: str) -> list[BookQuote]:
        if not self.settings.odds_api_key:
            return []
        sport = LEAGUES[league]["sport"]
        response = self._client.get(
            f"{ODDS_API}/sports/{sport}/odds",
            params={
                "apiKey": self.settings.odds_api_key,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "american",
            },
        )
        if response.status_code >= 400:
            return []
        quotes: list[BookQuote] = []
        for game in response.json():
            home = game.get("home_team") or ""
            away = game.get("away_team") or ""
            bookmakers = game.get("bookmakers") or []
            if not bookmakers:
                continue
            markets = bookmakers[0].get("markets") or []
            h2h = next((market for market in markets if market.get("key") == "h2h"), None)
            if not h2h:
                continue
            outcomes = {item.get("name"): item.get("price") for item in h2h.get("outcomes") or []}
            if home not in outcomes or away not in outcomes:
                continue
            raw = [american_to_prob(int(outcomes[away])), american_to_prob(int(outcomes[home]))]
            fair = devig(raw)
            quotes.append(
                BookQuote(
                    sport=sport,
                    home=home,
                    away=away,
                    away_prob=fair[0],
                    home_prob=fair[1],
                )
            )
        return quotes


def match_quote(event: EventMarkets, quotes: list[BookQuote]) -> BookQuote | None:
    names = [market.team for market in event.markets]
    title = event.title
    for quote in quotes:
        home_hit = any(names_match(name, quote.home) for name in names) or names_match(title, quote.home)
        away_hit = any(names_match(name, quote.away) for name in names) or names_match(title, quote.away)
        if home_hit and away_hit:
            return quote
    return None


def sportsbook_signals(events: list[EventMarkets], quotes_by_league: dict[str, list[BookQuote]], min_edge: float) -> list[Signal]:
    found: list[Signal] = []
    for event in events:
        quote = match_quote(event, quotes_by_league.get(event.league, []))
        if quote is None:
            continue
        for market in event.markets:
            fair = None
            if names_match(market.team, quote.home):
                fair = quote.home_prob
            elif names_match(market.team, quote.away):
                fair = quote.away_prob
            if fair is None:
                continue
            signal = sportsbook_value_signal(market, event, fair, min_edge)
            if signal:
                found.append(signal)
    return found
