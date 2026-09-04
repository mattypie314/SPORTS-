"""Book-line adapters and no-vig consensus. Primary fair value lives here."""

from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import httpx

from mlbkalshi.config import Settings
from mlbkalshi.names import team_code, team_code_from_text
from mlbkalshi.odds import american_to_implied, no_vig

ODDS_API = "https://api.the-odds-api.com/v4"
ODDS_SPORT = "baseball_mlb"
ET = ZoneInfo("America/New_York")

# Prefer these when present; otherwise median every remaining book.
SHARP_BOOKS = {
    "pinnacle",
    "circa",
    "circa_sports",
    "lowvig",
    "betonlineag",
    "bookmaker",
}

MARKET_ALIASES = {
    "h2h": "h2h",
    "ml": "h2h",
    "moneyline": "h2h",
    "spreads": "spreads",
    "spread": "spreads",
    "runline": "spreads",
    "totals": "totals",
    "total": "totals",
    "ou": "totals",
    "rfi": "rfi",
    "nrfi": "rfi",
    "f5spreads": "f5spreads",
    "f5spread": "f5spreads",
    "f5": "f5spreads",
}


@dataclass(frozen=True)
class BookOutcome:
    book: str
    market: str
    date_key: str
    away: str
    home: str
    outcome: str
    point: float | None
    american: int
    implied: float


@dataclass(frozen=True)
class ConsensusFair:
    fair: float
    source: str
    disagree_pts: float
    books: tuple[str, ...]
    deep: bool
    market: str
    outcome: str
    point: float | None
    date_key: str
    away: str
    home: str


def _norm_market(value: str) -> str:
    key = (value or "").strip().lower()
    if key not in MARKET_ALIASES:
        raise ValueError(f"unsupported book market: {value}")
    return MARKET_ALIASES[key]


def _norm_outcome(value: str, market: str) -> str:
    raw = (value or "").strip()
    if market in {"totals", "rfi"}:
        token = raw.upper()
        if token in {"OVER", "O", "YES", "Y"}:
            return "OVER"
        if token in {"UNDER", "U", "NO", "N"}:
            return "UNDER"
        raise ValueError(f"totals/rfi outcome must be OVER/UNDER, got {value}")
    code = team_code(raw) or team_code_from_text(raw)
    if not code:
        raise ValueError(f"unknown team outcome: {value}")
    return code


def _point(value: object) -> float | None:
    if value is None or value == "":
        return None
    return round(float(value), 2)


def et_date_key(value: datetime | str) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if len(raw) == 10 and raw[4] == "-":
            return raw
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ET).date().isoformat()


def _outcome_from_row(
    *,
    book: str,
    market: str,
    date_key: str,
    away: str,
    home: str,
    outcome: str,
    point: float | None,
    american: int,
) -> BookOutcome:
    implied = american_to_implied(american)
    return BookOutcome(
        book=book.strip().lower(),
        market=market,
        date_key=date_key,
        away=away,
        home=home,
        outcome=outcome,
        point=point,
        american=int(american),
        implied=implied,
    )


def parse_book_row(row: dict[str, Any]) -> BookOutcome:
    market = _norm_market(str(row.get("market") or "h2h"))
    away = team_code(str(row.get("away") or "")) or team_code_from_text(str(row.get("away") or ""))
    home = team_code(str(row.get("home") or "")) or team_code_from_text(str(row.get("home") or ""))
    if not away or not home:
        raise ValueError(f"could not resolve teams in {row}")
    commence = row.get("commence") or row.get("commence_time") or row.get("date")
    if not commence:
        raise ValueError("book row needs commence/date")
    date_key = et_date_key(commence)
    american = int(row.get("american") if row.get("american") is not None else row["price"])
    outcome = _norm_outcome(str(row.get("outcome") or row.get("name") or ""), market)
    return _outcome_from_row(
        book=str(row.get("book") or row.get("bookmaker") or "file"),
        market=market,
        date_key=date_key,
        away=away,
        home=home,
        outcome=outcome,
        point=_point(row.get("point") if row.get("point") is not None else row.get("line")),
        american=american,
    )


def load_book_file(path: str | Path) -> list[BookOutcome]:
    target = Path(path)
    if not target.exists():
        raise FileNotFoundError(f"book lines file not found: {target}")
    text = target.read_text()
    if target.suffix.lower() == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
    else:
        payload = json.loads(text)
        rows = payload if isinstance(payload, list) else payload.get("lines") or payload.get("books") or []
    out: list[BookOutcome] = []
    for row in rows:
        try:
            out.append(parse_book_row(row))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _odds_api_outcomes(game: dict, book: dict) -> Iterable[BookOutcome]:
    home_name = game.get("home_team") or ""
    away_name = game.get("away_team") or ""
    away = team_code(away_name) or team_code_from_text(away_name)
    home = team_code(home_name) or team_code_from_text(home_name)
    if not away or not home:
        return
    date_key = et_date_key(str(game.get("commence_time") or ""))
    book_key = str(book.get("key") or book.get("title") or "book")
    for market in book.get("markets") or []:
        key = str(market.get("key") or "")
        if key not in {"h2h", "spreads", "totals"}:
            continue
        for item in market.get("outcomes") or []:
            try:
                name = str(item.get("name") or "")
                if key == "totals":
                    outcome = _norm_outcome(name, "totals")
                else:
                    outcome = _norm_outcome(name, key)
                yield _outcome_from_row(
                    book=book_key,
                    market=key,
                    date_key=date_key,
                    away=away,
                    home=home,
                    outcome=outcome,
                    point=_point(item.get("point")),
                    american=int(item["price"]),
                )
            except (KeyError, TypeError, ValueError):
                continue


def fetch_odds_api(api_key: str, *, client: httpx.Client | None = None) -> list[BookOutcome]:
    if not api_key:
        return []
    owns = client is None
    http = client or httpx.Client(timeout=25.0, headers={"User-Agent": "mlbkalshi/0.1"})
    try:
        response = http.get(
            f"{ODDS_API}/sports/{ODDS_SPORT}/odds",
            params={
                "apiKey": api_key,
                "regions": "us,eu",
                "markets": "h2h,spreads,totals",
                "oddsFormat": "american",
            },
        )
        if response.status_code >= 400:
            return []
        games = response.json()
    finally:
        if owns:
            http.close()
    out: list[BookOutcome] = []
    for game in games or []:
        for book in game.get("bookmakers") or []:
            out.extend(_odds_api_outcomes(game, book))
    return out


def _median_for_outcome(used: dict[str, dict[str, float]], outcome: str) -> tuple[float, float] | None:
    values = [probs[outcome] for probs in used.values() if outcome in probs]
    if not values:
        return None
    disagree = (max(values) - min(values)) * 100.0
    return statistics.median(values), disagree


class FairIndex:
    """Lookup consensus by date + team codes + market + outcome + line."""

    def __init__(self) -> None:
        self._rows: dict[tuple, ConsensusFair] = {}

    def __len__(self) -> int:
        return len(self._rows)

    def add(self, row: ConsensusFair) -> None:
        self._rows[self._key(row.date_key, row.away, row.home, row.market, row.outcome, row.point)] = row

    @staticmethod
    def _key(
        date_key: str,
        away: str,
        home: str,
        market: str,
        outcome: str,
        point: float | None,
    ) -> tuple:
        teams = tuple(sorted((away, home)))
        line = None if point is None else round(float(point), 2)
        return (date_key, teams, market, outcome, line)

    def lookup(
        self,
        *,
        date_key: str,
        away: str,
        home: str,
        market: str,
        outcome: str,
        point: float | None = None,
    ) -> ConsensusFair | None:
        return self._rows.get(self._key(date_key, away, home, market, outcome, point))

    @classmethod
    def build(cls, outcomes: Iterable[BookOutcome]) -> FairIndex:
        index = cls()
        rows = list(outcomes)
        grouped: dict[tuple, list[BookOutcome]] = {}
        for row in rows:
            teams = tuple(sorted((row.away, row.home)))
            line = None
            if row.market in {"spreads", "f5spreads"} and row.point is not None:
                line = round(abs(row.point), 2)
            elif row.point is not None:
                line = round(row.point, 2)
            grouped.setdefault((row.date_key, teams, row.market, line, row.book), []).append(row)

        by_game: dict[tuple, dict[str, dict[str, float]]] = {}
        meta: dict[tuple, BookOutcome] = {}
        for (date_key, teams, market, line, book), legs in grouped.items():
            if len(legs) < 2:
                continue
            try:
                probs = no_vig([leg.american for leg in legs])
            except ValueError:
                continue
            game = (date_key, teams, market, line)
            by_game.setdefault(game, {})[book] = {leg.outcome: probs[i] for i, leg in enumerate(legs)}
            meta.setdefault(game, legs[0])

        for game, fairs in by_game.items():
            date_key, teams, market, line = game
            sample = meta[game]
            sharp = {book: values for book, values in fairs.items() if book in SHARP_BOOKS}
            used = sharp or fairs
            books = tuple(sorted(used))
            deep = any(book in SHARP_BOOKS for book in used)
            if "pinnacle" in used:
                source = "pinnacle"
            elif "circa" in used or "circa_sports" in used:
                source = "circa"
            elif sharp:
                source = "sharp_median"
            else:
                source = "book_median"
            outcomes_seen = {outcome for probs in used.values() for outcome in probs}
            for outcome in outcomes_seen:
                packed = _median_for_outcome(used, outcome)
                if packed is None:
                    continue
                fair, disagree = packed
                point = None
                if market in {"spreads", "f5spreads"}:
                    point = _signed_point(rows, date_key, teams, market, outcome, line)
                elif line is not None:
                    point = line
                index.add(
                    ConsensusFair(
                        fair=fair,
                        source=source,
                        disagree_pts=round(disagree, 2),
                        books=books,
                        deep=deep,
                        market=market,
                        outcome=outcome,
                        point=point,
                        date_key=date_key,
                        away=sample.away,
                        home=sample.home,
                    )
                )
        return index


def _signed_point(
    outcomes: Iterable[BookOutcome],
    date_key: str,
    teams: tuple[str, str],
    market: str,
    outcome: str,
    abs_line: float | None,
) -> float | None:
    if abs_line is None:
        return None
    for row in outcomes:
        if (
            row.date_key == date_key
            and tuple(sorted((row.away, row.home))) == teams
            and row.market == market
            and row.outcome == outcome
            and row.point is not None
            and abs(row.point) == abs_line
        ):
            return round(row.point, 2)
    return abs_line


def load_fair_index(settings: Settings, *, client: httpx.Client | None = None) -> FairIndex:
    rows: list[BookOutcome] = []
    if settings.books_path:
        rows.extend(load_book_file(settings.books_path))
    if settings.odds_api_key:
        rows.extend(fetch_odds_api(settings.odds_api_key, client=client))
    return FairIndex.build(rows)
