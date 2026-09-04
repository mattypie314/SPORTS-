from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Sequence

from sportsbot.config import Settings
from sportsbot.kalshi.models import EventMarkets, format_american
from sportsbot.live import LiveTradingDisabled, place_signal_orders, require_live
from sportsbot.paper import PaperBook
from sportsbot.service import scan_board
from sportsbot.signals import Signal


def _settings() -> Settings:
    return Settings()


def _scan(settings: Settings) -> tuple[list[EventMarkets], list[Signal]]:
    return scan_board(settings)


def _print_board(events: list[EventMarkets]) -> None:
    if not events:
        print("No open MLB games found.")
        return
    print(f"{'KICKOFF':<22} {'GAME':<42} {'TEAM':<22} {'BID':>6} {'ASK':>6} {'MID':>6} {'AMER':>7} {'VOL':>10}")
    print("-" * 130)
    for event in events:
        kickoff = event.kickoff.strftime("%Y-%m-%d %H:%M") if event.kickoff else "—"
        for market in event.markets:
            mid = f"{market.mid:.2f}" if market.mid is not None else "—"
            bid = f"{market.yes_bid:.2f}" if market.yes_bid is not None else "—"
            ask = f"{market.yes_ask:.2f}" if market.yes_ask is not None else "—"
            print(
                f"{kickoff:<22} {event.title[:42]:<42} "
                f"{market.team[:22]:<22} {bid:>6} {ask:>6} {mid:>6} "
                f"{format_american(market.american):>7} {market.volume:>10.0f}"
            )


def _print_signals(signals: list[Signal]) -> None:
    if not signals:
        print("No signals above the current thresholds.")
        return
    print(f"{'KIND':<18} {'EDGE':>7} SUMMARY")
    print("-" * 110)
    for signal in signals:
        print(f"{signal.kind:<18} {signal.edge:>6.1%} {signal.summary}")


def cmd_scan(args: argparse.Namespace) -> int:
    settings = _settings()
    events, signals = _scan(settings)
    if args.json:
        print(json.dumps({"events": [event.to_dict() for event in events], "signals": [s.to_dict() for s in signals]}, indent=2))
        return 0
    print(f"Open MLB games: {len(events)}")
    _print_board(events)
    print()
    print(f"Signals: {len(signals)}")
    _print_signals(signals)
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    settings = _settings()
    _, signals = _scan(settings)
    if args.json:
        print(json.dumps([signal.to_dict() for signal in signals], indent=2))
        return 0
    _print_signals(signals)
    return 0


def cmd_paper(args: argparse.Namespace) -> int:
    settings = _settings()
    book = PaperBook(settings)
    if args.status:
        print(json.dumps(book.status(), indent=2) if args.json else _format_status(book.status()))
        return 0
    events, signals = _scan(settings)
    actionable = [signal for signal in signals if signal.kind in {"arb_buy", "arb_sell", "sportsbook_value"}]
    fills = book.execute_actionable(actionable, events)
    payload = {
        "signals": [signal.to_dict() for signal in actionable],
        "fills": [fill.to_dict() for fill in fills],
        "status": book.status(),
    }
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Actionable signals: {len(actionable)}")
        _print_signals(actionable)
        print()
        print(f"Paper fills: {len(fills)}")
        for fill in fills:
            print(f"  {fill.side.upper()} {fill.contracts:.2f} {fill.ticker} @ {fill.price:.2f} (${fill.notional:.2f})")
        if not fills:
            print("  none (no edge, or risk limits blocked the trade)")
        print()
        print(_format_status(book.status()))
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    settings = _settings()
    book = PaperBook(settings) if args.paper else None
    while True:
        events, signals = _scan(settings)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{stamp}] {len(events)} MLB games, {len(signals)} signals")
        _print_signals(signals)
        if book is not None:
            fills = book.execute_actionable(
                [signal for signal in signals if signal.kind in {"arb_buy", "arb_sell", "sportsbook_value"}],
                events,
            )
            if fills:
                print(f"Paper fills this pass: {len(fills)}")
        if args.once:
            return 0
        time.sleep(args.interval)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    import uvicorn

    from sportsbot.dashboard.app import create_app

    app = create_app(_settings())
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def cmd_live(args: argparse.Namespace) -> int:
    settings = _settings()
    try:
        require_live(settings)
    except LiveTradingDisabled as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not args.confirm_live:
        print("Refusing to send live orders without --confirm-live.", file=sys.stderr)
        return 2
    events, signals = _scan(settings)
    actionable = [signal for signal in signals if signal.kind in {"arb_buy", "sportsbook_value"}]
    if args.dry_run:
        print(json.dumps([signal.to_dict() for signal in actionable], indent=2))
        return 0
    placed = []
    for signal in actionable:
        placed.extend(place_signal_orders(settings, signal, events))
    print(json.dumps(placed, indent=2))
    return 0


def _format_status(status: dict) -> str:
    lines = [
        f"Mode: {status['mode']}",
        f"Cash: ${status['cash']:.2f} (started ${status['starting_bankroll']:.2f})",
        f"Open events: {status['open_positions']}",
        f"Spent today: ${status['spent_today']:.2f} (remaining ${status['remaining_daily']:.2f})",
        f"Kill switch: {'ON' if status['kill_switch'] else 'off'}",
        f"Fills: {len(status['fills'])}",
    ]
    return "\n".join(lines)


def _add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sportsbot",
        description="Kalshi MLB bot: scan game winners, find edges, paper-trade by default.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Show the live MLB board and signals")
    _add_json_flag(scan)
    scan.set_defaults(func=cmd_scan)

    signals = sub.add_parser("signals", help="Show only signals")
    _add_json_flag(signals)
    signals.set_defaults(func=cmd_signals)

    paper = sub.add_parser("paper", help="Scan and paper-trade actionable MLB signals")
    _add_json_flag(paper)
    paper.add_argument("--status", action="store_true", help="Print the paper book and exit")
    paper.set_defaults(func=cmd_paper)

    watch = sub.add_parser("watch", help="Rescan MLB on an interval")
    _add_json_flag(watch)
    watch.add_argument("--interval", type=int, default=60, help="Seconds between scans")
    watch.add_argument("--paper", action="store_true", help="Paper-trade each pass")
    watch.add_argument("--once", action="store_true", help="Run a single pass")
    watch.set_defaults(func=cmd_watch)

    dash = sub.add_parser("dashboard", help="Open the local MLB terminal")
    dash.add_argument("--host", default="127.0.0.1")
    dash.add_argument("--port", type=int, default=8000)
    dash.set_defaults(func=cmd_dashboard)

    live = sub.add_parser("live", help="Send real Kalshi orders (disabled unless env flags are set)")
    _add_json_flag(live)
    live.add_argument("--confirm-live", action="store_true", help="Required to actually send orders")
    live.add_argument("--dry-run", action="store_true", help="Print would-be live orders only")
    live.set_defaults(func=cmd_live)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1
