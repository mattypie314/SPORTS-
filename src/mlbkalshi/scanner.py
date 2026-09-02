"""Slate scanner. Books first; standings model is low_confidence fallback."""

from __future__ import annotations

from dataclasses import dataclass

from mlbkalshi.fees import EdgeResult, evaluate
from mlbkalshi.kalshi_public import MLB_SERIES, KalshiPublic
from mlbkalshi.model_fair import load_model_fairs, model_win_prob
from mlbkalshi.names import codes_from_event_title, team_code
from mlbkalshi.odds import remove_vig


def _dollars(value: object) -> float | None:
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


def _active_markets(event: dict) -> list[dict]:
    return [m for m in (event.get("markets") or []) if m.get("status") in {"active", "open"}]


def scan_series(
    client: KalshiPublic,
    series: str,
    bankroll: float,
    *,
    book_fairs: dict[str, dict] | None = None,
) -> list[ScannedRow]:
    events = client.list_events(series)
    models = None if book_fairs else load_model_fairs()
    rows: list[ScannedRow] = []
    for event in events:
        title = event.get("title") or ""
        away, home = codes_from_event_title(title)
        markets = _active_markets(event)
        if series == "KXMLBGAME":
            rows.extend(
                _scan_moneyline(event, markets, away, home, bankroll, book_fairs, models)
            )
        else:
            # Phase 3+ book matching fills these in. Without books they stay model-less.
            continue
    rows.sort(key=lambda row: row.result.net_ev, reverse=True)
    return rows


def _scan_moneyline(
    event: dict,
    markets: list[dict],
    away: str | None,
    home: str | None,
    bankroll: float,
    book_fairs: dict[str, dict] | None,
    models,
) -> list[ScannedRow]:
    rows: list[ScannedRow] = []
    legs: list[tuple[dict, str | None]] = []
    for market in markets:
        label = market.get("yes_sub_title") or market.get("title") or ""
        code = team_code(label) or (away if away and away.lower() in label.lower() else None)
        if code is None:
            code = team_code(label)
        legs.append((market, code))

    model_probs: dict[str, float] = {}
    if models is not None:
        for _market, code in legs:
            if code and model_win_prob(code, models) is not None:
                model_probs[code] = model_win_prob(code, models)  # type: ignore[arg-type]
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
        book = None
        if book_fairs and code:
            book = book_fairs.get(f"{event.get('event_ticker')}:{code}") or book_fairs.get(code)
        if book:
            fair = float(book["fair"])
            source = str(book.get("source", "book"))
            disagree = float(book.get("disagree_pts", 0.0))
            low = False
        elif code and code in model_probs:
            fair = model_probs[code]
            source = "model_fair"
            disagree = 0.0
            low = True
        else:
            continue
        result = evaluate(
            fair=fair,
            kalshi_yes=ask,
            side="yes",
            bankroll=bankroll,
            maker=False,
            spread=spread,
            disagree_pts=disagree,
            source_of_fair=source,
            low_confidence=low,
        )
        why = (
            f"{source} {fair:.3f} vs Kalshi ask {ask:.2f} "
            f"({result.reason})"
        )
        rows.append(
            ScannedRow(
                result=result,
                team=code or label,
                why=why,
                event_ticker=event.get("event_ticker") or "",
                ticker=market.get("ticker") or "",
            )
        )
    return rows


def scan_slate(bankroll: float, series: list[str] | None = None) -> list[ScannedRow]:
    chosen = series or ["KXMLBGAME"]
    unknown = [item for item in chosen if item not in MLB_SERIES]
    if unknown:
        raise ValueError(f"unsupported series: {', '.join(unknown)}")
    rows: list[ScannedRow] = []
    with KalshiPublic() as client:
        for ticker in chosen:
            rows.extend(scan_series(client, ticker, bankroll))
    rows.sort(key=lambda row: row.result.net_ev, reverse=True)
    return rows
