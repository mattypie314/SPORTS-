"""Slate scanner. Books first; standings model is low_confidence fallback."""

from __future__ import annotations

from dataclasses import dataclass

from mlbkalshi.config import Settings
from mlbkalshi.fair import ConsensusFair, FairIndex, load_fair_index
from mlbkalshi.fees import FAVORITE_CUTOFF, LONGSHOT_CUTOFF, EdgeResult, evaluate
from mlbkalshi.kalshi_public import MLB_SERIES, KalshiPublic
from mlbkalshi.live import looks_like_optional_playoff_game
from mlbkalshi.model_fair import load_model_fairs, model_win_prob
from mlbkalshi.names import (
    codes_from_event_title,
    event_date_from_ticker,
    parse_ticker,
    team_code,
    team_code_from_text,
)
from mlbkalshi.odds import remove_vig


def _dollars(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _floor(market: dict) -> float | None:
    value = market.get("floor_strike")
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ScannedRow:
    result: EdgeResult
    team: str
    why: str
    event_ticker: str
    ticker: str
    series: str


def _active_markets(event: dict) -> list[dict]:
    return [m for m in (event.get("markets") or []) if m.get("status") in {"active", "open"}]


def event_is_lopsided(markets: list[dict]) -> bool:
    """Treat 80¢+ / 15¢ books as live or decided — do not average into 9-inning contracts."""
    for market in markets:
        ask = _dollars(market.get("yes_ask_dollars"))
        bid = _dollars(market.get("yes_bid_dollars"))
        for price in (ask, bid):
            if price is None:
                continue
            if price >= FAVORITE_CUTOFF or price <= LONGSHOT_CUTOFF:
                return True
    return False


def _date_key(event: dict) -> str | None:
    ticker = event.get("event_ticker") or ""
    parsed = event_date_from_ticker(ticker)
    return parsed.isoformat() if parsed else None


def _evaluate(
    *,
    fair: float,
    ask: float,
    side: str,
    bankroll: float,
    spread: float | None,
    source: str,
    disagree: float,
    low: bool,
    deep: bool,
    team: str,
    why: str,
    event: dict,
    market: dict,
    series: str,
) -> ScannedRow:
    result = evaluate(
        fair=fair,
        kalshi_yes=ask,
        side=side,
        bankroll=bankroll,
        maker=False,
        spread=spread,
        disagree_pts=disagree,
        source_of_fair=source,
        low_confidence=low,
        deep=deep,
    )
    title = event.get("title") or ""
    if looks_like_optional_playoff_game(title):
        why = f"{why}; playoff Game 5/6/7 may mark to last fair — not a sportsbook void"
    return ScannedRow(
        result=result,
        team=team,
        why=why,
        event_ticker=event.get("event_ticker") or "",
        ticker=market.get("ticker") or "",
        series=series,
    )


def _book_or_none(
    fairs: FairIndex | None,
    *,
    date_key: str | None,
    away: str | None,
    home: str | None,
    market: str,
    outcome: str,
    point: float | None = None,
) -> ConsensusFair | None:
    if fairs is None or not date_key or not away or not home:
        return None
    return fairs.lookup(
        date_key=date_key,
        away=away,
        home=home,
        market=market,
        outcome=outcome,
        point=point,
    )


def scan_events(
    events: list[dict],
    series: str,
    bankroll: float,
    *,
    fairs: FairIndex | None = None,
    models=None,
) -> list[ScannedRow]:
    rows: list[ScannedRow] = []
    for event in events:
        title = event.get("title") or ""
        away, home = codes_from_event_title(title)
        if (away is None or home is None) and event.get("event_ticker"):
            from mlbkalshi.names import teams_from_ticker

            away, home = teams_from_ticker(event["event_ticker"])
        markets = _active_markets(event)
        date_key = _date_key(event)
        if series in {"KXMLBGAME", "KXMLBSPREAD", "KXMLBTOTAL"} and event_is_lopsided(markets):
            continue
        if series == "KXMLBGAME":
            rows.extend(_scan_moneyline(event, markets, away, home, date_key, bankroll, fairs, models))
        elif series in {"KXMLBSPREAD", "KXMLBF5SPREAD"}:
            book_market = "f5spreads" if series == "KXMLBF5SPREAD" else "spreads"
            rows.extend(_scan_spread(event, markets, away, home, date_key, bankroll, fairs, book_market, series))
        elif series == "KXMLBTOTAL":
            rows.extend(_scan_total(event, markets, away, home, date_key, bankroll, fairs))
        elif series == "KXMLBRFI":
            rows.extend(_scan_rfi(event, markets, away, home, date_key, bankroll, fairs))
    rows.sort(key=lambda row: row.result.net_ev, reverse=True)
    return rows


def _scan_moneyline(
    event: dict,
    markets: list[dict],
    away: str | None,
    home: str | None,
    date_key: str | None,
    bankroll: float,
    fairs: FairIndex | None,
    models,
) -> list[ScannedRow]:
    rows: list[ScannedRow] = []
    legs: list[tuple[dict, str | None]] = []
    for market in markets:
        label = market.get("yes_sub_title") or market.get("title") or ""
        code = team_code(label) or team_code_from_text(label)
        if code is None and away and away.lower() in label.lower():
            code = away
        if code is None and home and home.lower() in label.lower():
            code = home
        outcome = parse_ticker(market.get("ticker") or "").outcome
        if code is None and outcome:
            code = team_code(outcome)
        legs.append((market, code))

    model_probs: dict[str, float] = {}
    if models is not None:
        for _market, code in legs:
            if code and model_win_prob(code, models) is not None:
                model_probs[code] = model_win_prob(code, models)  # type: ignore[assignment]
        if len(model_probs) >= 2:
            codes = list(model_probs)
            vig_free = remove_vig([model_probs[c] for c in codes])
            model_probs = {code: vig_free[i] for i, code in enumerate(codes)}

    for market, code in legs:
        ask = _dollars(market.get("yes_ask_dollars"))
        bid = _dollars(market.get("yes_bid_dollars"))
        if ask is None:
            continue
        spread = (ask - bid) if bid is not None else None
        label = market.get("yes_sub_title") or code or "?"
        book = _book_or_none(
            fairs, date_key=date_key, away=away, home=home, market="h2h", outcome=code or ""
        )
        if book:
            fair = book.fair
            source = book.source
            disagree = book.disagree_pts
            low = False
            deep = book.deep
        elif code and code in model_probs:
            fair = model_probs[code]
            source = "model_fair"
            disagree = 0.0
            low = True
            deep = False
        else:
            continue
        why = f"{source} {fair:.3f} vs Kalshi ask {ask:.2f} ({event.get('title')})"
        rows.append(
            _evaluate(
                fair=fair,
                ask=ask,
                side="yes",
                bankroll=bankroll,
                spread=spread,
                source=source,
                disagree=disagree,
                low=low,
                deep=deep,
                team=code or label,
                why=why,
                event=event,
                market=market,
                series="KXMLBGAME",
            )
        )
    return rows


def _scan_spread(
    event: dict,
    markets: list[dict],
    away: str | None,
    home: str | None,
    date_key: str | None,
    bankroll: float,
    fairs: FairIndex | None,
    book_market: str,
    series: str,
) -> list[ScannedRow]:
    if fairs is None:
        return []
    rows: list[ScannedRow] = []
    for market in markets:
        ask = _dollars(market.get("yes_ask_dollars"))
        bid = _dollars(market.get("yes_bid_dollars"))
        if ask is None:
            continue
        label = market.get("yes_sub_title") or market.get("title") or ""
        code = team_code_from_text(label) or team_code(label)
        floor = _floor(market)
        if code is None or floor is None:
            continue
        book_point = -floor
        book = _book_or_none(
            fairs,
            date_key=date_key,
            away=away,
            home=home,
            market=book_market,
            outcome=code,
            point=book_point,
        )
        if book is None:
            continue
        why = (
            f"{book.source} {code} {book_point:+.1f} fair {book.fair:.3f} "
            f"vs Kalshi ask {ask:.2f}"
        )
        rows.append(
            _evaluate(
                fair=book.fair,
                ask=ask,
                side="yes",
                bankroll=bankroll,
                spread=(ask - bid) if bid is not None else None,
                source=book.source,
                disagree=book.disagree_pts,
                low=False,
                deep=book.deep,
                team=f"{code} {book_point:+.1f}",
                why=why,
                event=event,
                market=market,
                series=series,
            )
        )
    return rows


def _scan_total(
    event: dict,
    markets: list[dict],
    away: str | None,
    home: str | None,
    date_key: str | None,
    bankroll: float,
    fairs: FairIndex | None,
) -> list[ScannedRow]:
    if fairs is None:
        return []
    rows: list[ScannedRow] = []
    for market in markets:
        ask = _dollars(market.get("yes_ask_dollars"))
        bid = _dollars(market.get("yes_bid_dollars"))
        if ask is None:
            continue
        floor = _floor(market)
        if floor is None:
            continue
        book = _book_or_none(
            fairs,
            date_key=date_key,
            away=away,
            home=home,
            market="totals",
            outcome="OVER",
            point=floor,
        )
        if book is None:
            continue
        for side, outcome in (("yes", "OVER"), ("no", "UNDER")):
            why = f"{book.source} {outcome} {floor} fair {book.fair if side == 'yes' else 1 - book.fair:.3f} vs Kalshi {side}"
            rows.append(
                _evaluate(
                    fair=book.fair,
                    ask=ask,
                    side=side,
                    bankroll=bankroll,
                    spread=(ask - bid) if bid is not None else None,
                    source=book.source,
                    disagree=book.disagree_pts,
                    low=False,
                    deep=book.deep,
                    team=f"{outcome} {floor}",
                    why=why,
                    event=event,
                    market=market,
                    series="KXMLBTOTAL",
                )
            )
    return rows


def _scan_rfi(
    event: dict,
    markets: list[dict],
    away: str | None,
    home: str | None,
    date_key: str | None,
    bankroll: float,
    fairs: FairIndex | None,
) -> list[ScannedRow]:
    if fairs is None:
        return []
    rows: list[ScannedRow] = []
    for market in markets:
        ask = _dollars(market.get("yes_ask_dollars"))
        bid = _dollars(market.get("yes_bid_dollars"))
        if ask is None:
            continue
        book = _book_or_none(
            fairs, date_key=date_key, away=away, home=home, market="rfi", outcome="OVER", point=0.5
        )
        if book is None:
            book = _book_or_none(
                fairs, date_key=date_key, away=away, home=home, market="rfi", outcome="OVER", point=None
            )
        if book is None:
            continue
        why = f"{book.source} RFI/Yes fair {book.fair:.3f} vs Kalshi ask {ask:.2f}"
        rows.append(
            _evaluate(
                fair=book.fair,
                ask=ask,
                side="yes",
                bankroll=bankroll,
                spread=(ask - bid) if bid is not None else None,
                source=book.source,
                disagree=book.disagree_pts,
                low=False,
                deep=book.deep,
                team="RFI YES",
                why=why,
                event=event,
                market=market,
                series="KXMLBRFI",
            )
        )
    return rows


def scan_series(
    client: KalshiPublic,
    series: str,
    bankroll: float,
    *,
    fairs: FairIndex | None = None,
    models=None,
) -> list[ScannedRow]:
    events = client.list_events(series)
    return scan_events(events, series, bankroll, fairs=fairs, models=models)


def scan_slate(
    bankroll: float,
    series: list[str] | None = None,
    *,
    settings: Settings | None = None,
    fairs: FairIndex | None = None,
) -> list[ScannedRow]:
    chosen = series or list(MLB_SERIES)
    unknown = [item for item in chosen if item not in MLB_SERIES]
    if unknown:
        raise ValueError(f"unsupported series: {', '.join(unknown)}")
    cfg = settings or Settings.from_env(bankroll)
    index = fairs if fairs is not None else load_fair_index(cfg)
    models = None if len(index) else load_model_fairs()
    rows: list[ScannedRow] = []
    with KalshiPublic() as client:
        for ticker in chosen:
            rows.extend(scan_series(client, ticker, bankroll, fairs=index if len(index) else None, models=models))
    rows.sort(key=lambda row: row.result.net_ev, reverse=True)
    return rows
