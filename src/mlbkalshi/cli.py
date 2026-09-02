from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from typing import Sequence

from mlbkalshi.config import Settings
from mlbkalshi.fair import load_fair_index
from mlbkalshi.fees import evaluate
from mlbkalshi.kalshi_public import MLB_SERIES, KalshiPublic
from mlbkalshi.live import KalshiSigned, LiveDisabled, looks_like_optional_playoff_game, place_limit_yes
from mlbkalshi.odds import no_vig
from mlbkalshi.paper import PaperBlocked, PaperLedger
from mlbkalshi.render import format_pass, print_slate
from mlbkalshi.scanner import scan_slate


def _settings(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env(getattr(args, "bankroll", None))
    books = getattr(args, "books", None)
    if books:
        settings = replace(settings, books_path=books)
    return settings


def cmd_edge(args: argparse.Namespace) -> int:
    settings = _settings(args)
    fair_legs = no_vig(list(args.book_odds))
    fair = fair_legs[0]
    result = evaluate(
        fair=fair,
        kalshi_yes=args.kalshi,
        side=args.side,
        bankroll=settings.bankroll,
        maker=bool(getattr(args, "maker", False)),
        source_of_fair="book",
    )
    why = (
        f"books {'/'.join(str(x) for x in args.book_odds)} no-vig {fair:.3f} "
        f"vs Kalshi {args.side} @ {result.price:.2f}"
    )
    if result.passed:
        print(format_pass(result, team="BOOK", why=why))
    else:
        print("No actionable edge")
        print()
        print(
            f"  FAIL  {args.side.upper()} @ {result.price:.2f}  "
            f"netEV {result.net_ev:+.1%}  {result.reason}"
        )
    print(
        f"fair={result.fair:.4f} price={result.price:.4f} "
        f"fee={result.fee:.4f} net_ev={result.net_ev:+.4f} "
        f"size={result.size.contracts:.2f}c risk=${result.size.risk:.2f}"
    )
    return 0


def cmd_markets(args: argparse.Namespace) -> int:
    series = args.series
    with KalshiPublic() as client:
        events = client.list_events(series)
    if args.json:
        print(json.dumps(events, indent=2))
        return 0
    print(f"{series} open events: {len(events)}")
    for event in events:
        title = event.get("title") or event.get("event_ticker")
        markets = [m for m in (event.get("markets") or []) if m.get("status") in {"active", "open"}]
        print(f"  {event.get('event_ticker')}  {title}  markets={len(markets)}")
        for market in markets:
            print(
                f"    {market.get('ticker')}  "
                f"{market.get('yes_sub_title') or market.get('title')}  "
                f"bid={market.get('yes_bid_dollars')} ask={market.get('yes_ask_dollars')}"
            )
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    settings = _settings(args)
    series = args.series or list(MLB_SERIES)
    fairs = load_fair_index(settings)
    rows = scan_slate(settings.bankroll, series, settings=settings, fairs=fairs)
    print_slate([(row.result, row.team, row.why) for row in rows])
    if not settings.odds_api_key and not settings.books_path:
        print()
        print("degraded: no ODDS_API_KEY / BOOK_LINES_PATH — rows use model_fair / low_confidence")
    elif len(fairs) == 0:
        print()
        print("degraded: book adapters returned no lines — rows use model_fair / low_confidence")
    if getattr(args, "paper", False):
        ledger = PaperLedger(settings)
        written = 0
        for row in rows:
            if not row.result.passed:
                continue
            try:
                ledger.record(row.ticker, row.result, why=row.why)
                written += 1
            except PaperBlocked as exc:
                print(f"paper skipped {row.ticker}: {exc}")
                break
        print(f"papered {written} PASS row(s)")
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    settings = _settings(args)
    ledger = PaperLedger(settings)
    if args.reset_kill:
        ledger.reset_kill()
        print("kill switch cleared")
    if args.settle:
        ticker, result = args.settle
        row = ledger.settle(ticker, result)
        print(f"settled {row.ticker} -> {row.result}")
    if args.status or not (args.reset_kill or args.settle):
        print(json.dumps(ledger.status(), indent=2))
    return 0


def cmd_portfolio(args: argparse.Namespace) -> int:
    del args
    settings = Settings.from_env()
    if not settings.has_keys:
        print("no Kalshi keys — portfolio is read-only when KALSHI_API_KEY_ID + KALSHI_PRIVATE_KEY_PATH are set")
        return 0
    with KalshiSigned(settings) as api:
        print(json.dumps({"balance": api.balance(), "positions": api.positions()}, indent=2, default=str))
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if args.dry_run or not args.confirm_live:
        print(
            "dry-run: would submit a limit Yes buy "
            f"ticker={args.ticker} price={args.price} count={args.count}. "
            "Live Create Order needs LIVE_TRADING=1, keys, and --confirm-live."
        )
        if looks_like_optional_playoff_game(args.ticker):
            print("warning: playoff Game 5/6/7 may resolve to last fair — not a sportsbook void")
        return 0
    try:
        payload = place_limit_yes(settings, ticker=args.ticker, price=args.price, contracts=args.count)
    except LiveDisabled as exc:
        print(f"live disabled: {exc}")
        return 2
    print(json.dumps(payload, indent=2, default=str))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mlbkalshi", description="Kalshi MLB +EV scanner")
    sub = parser.add_subparsers(dest="command", required=True)

    edge = sub.add_parser("edge", help="No-vig book odds vs one Kalshi price")
    edge.add_argument("--book-odds", nargs="+", required=True, type=int)
    edge.add_argument("--kalshi", required=True, type=float)
    edge.add_argument("--side", choices=("yes", "no"), default="yes")
    edge.add_argument("--bankroll", type=float, default=None)
    edge.add_argument("--maker", action="store_true")
    edge.set_defaults(func=cmd_edge)

    markets = sub.add_parser("markets", help="List open Kalshi MLB markets")
    markets.add_argument("--series", default="KXMLBGAME", choices=list(MLB_SERIES))
    markets.add_argument("--json", action="store_true")
    markets.set_defaults(func=cmd_markets)

    scan = sub.add_parser("scan", help="Scan the MLB slate")
    scan.add_argument("--bankroll", type=float, default=None)
    scan.add_argument("--series", action="append", choices=list(MLB_SERIES))
    scan.add_argument("--books", help="CSV/JSON book-line drop (overrides BOOK_LINES_PATH)")
    scan.add_argument("--paper", action="store_true", help="Write PASS rows to the paper ledger")
    scan.set_defaults(func=cmd_scan)

    paper = sub.add_parser("paper", help="Paper ledger status / settle / reset kill")
    paper.add_argument("--status", action="store_true")
    paper.add_argument("--reset-kill", action="store_true")
    paper.add_argument("--settle", nargs=2, metavar=("TICKER", "RESULT"), help="RESULT = win|lose|void")
    paper.add_argument("--bankroll", type=float, default=None)
    paper.set_defaults(func=cmd_paper)

    portfolio = sub.add_parser("portfolio", help="Read-only Kalshi portfolio (keys required)")
    portfolio.set_defaults(func=cmd_portfolio)

    live = sub.add_parser("live", help="Create Order — disabled unless LIVE_TRADING=1")
    live.add_argument("--ticker", required=True)
    live.add_argument("--price", required=True, type=float)
    live.add_argument("--count", type=int, default=1)
    live.add_argument("--dry-run", action="store_true")
    live.add_argument("--confirm-live", action="store_true")
    live.set_defaults(func=cmd_live)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
