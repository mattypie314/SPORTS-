#!/usr/bin/env python3
"""Compute no-vig book fair vs a Kalshi Yes/No price.

Phase 1+ delegates to mlbkalshi so this script and `python -m mlbkalshi edge`
stay identical.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main(argv: list[str] | None = None) -> int:
    try:
        from mlbkalshi.cli import cmd_edge
    except ImportError:
        return _standalone(argv)

    parser = argparse.ArgumentParser(description="Kalshi vs no-vig book edge")
    parser.add_argument("--book-odds", nargs="+", required=True, type=int, help="American odds, two-way or multi-way")
    parser.add_argument("--kalshi", required=True, type=float, help="Kalshi Yes price in dollars (0-1)")
    parser.add_argument("--side", choices=("yes", "no"), default="yes")
    parser.add_argument("--bankroll", type=float, default=None)
    parser.add_argument("--maker", action="store_true", help="Price as a resting maker")
    args = parser.parse_args(argv)
    return cmd_edge(args)


def _standalone(argv: list[str] | None) -> int:
    """Used only if mlbkalshi is not importable yet."""
    parser = argparse.ArgumentParser(description="Kalshi vs no-vig book edge (standalone)")
    parser.add_argument("--book-odds", nargs="+", required=True, type=int)
    parser.add_argument("--kalshi", required=True, type=float)
    parser.add_argument("--side", choices=("yes", "no"), default="yes")
    parser.add_argument("--bankroll", type=float, default=100.0)
    parser.add_argument("--maker", action="store_true")
    args = parser.parse_args(argv)

    def implied(american: int) -> float:
        if american > 0:
            return 100.0 / (american + 100.0)
        return abs(american) / (abs(american) + 100.0)

    raw = [implied(x) for x in args.book_odds]
    total = sum(raw)
    fair_legs = [x / total for x in raw]
    fair = fair_legs[0] if args.side == "yes" else 1.0 - fair_legs[0]
    if args.side == "no":
        price = 1.0 - args.kalshi
    else:
        price = args.kalshi
    rate = 0.0175 if args.maker else 0.07
    fee = rate * price * (1.0 - price)
    net = fair - price - fee
    print(f"fair={fair:.4f} price={price:.4f} fee={fee:.4f} net_ev={net:+.4f}")
    if net >= 0.06:
        print("PASS")
    else:
        print("No actionable edge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
