from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from mlbkalshi.config import Settings
from mlbkalshi.fees import evaluate
from mlbkalshi.kalshi_public import MLB_SERIES, KalshiPublic
from mlbkalshi.odds import no_vig
from mlbkalshi.render import format_pass, print_slate
from mlbkalshi.scanner import scan_slate


def cmd_edge(args: argparse.Namespace) -> int:
    settings = Settings.from_env(getattr(args, "bankroll", None))
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
    settings = Settings.from_env(args.bankroll)
    series = args.series or ["KXMLBGAME"]
    rows = scan_slate(settings.bankroll, series)
    print_slate([(row.result, row.team, row.why) for row in rows])
    if not settings.odds_api_key:
        print()
        print("degraded: no ODDS_API_KEY — rows use model_fair / low_confidence")
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
    scan.set_defaults(func=cmd_scan)

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
