"""PASS boxes and closest-miss tables from AGENTS.md."""

from __future__ import annotations

from mlbkalshi.fees import EdgeResult


def _box_line(text: str, width: int = 62) -> str:
    body = text[: width - 2]
    return "│ " + body.ljust(width - 2) + "│"


def format_pass(result: EdgeResult, *, team: str, why: str) -> str:
    lines = [
        "┌" + "─" * 62 + "┐",
        _box_line(f"PASS   {team} {result.side.upper()} @ {result.price:.2f}"),
        _box_line(
            f"Fair   {result.fair:.3f}  ({result.source_of_fair})  Δbooks {result.disagree_pts:.1f}"
        ),
        _box_line(
            f"NetEV  {result.net_ev:+.1%}  fee {result.fee:.3f}  "
            f"{'maker' if result.maker else 'taker'}"
        ),
        _box_line(
            f"Size   {result.size.contracts:.2f}c   risk ${result.size.risk:.2f}   "
            f"Kelly {result.size.kelly_used:.2f}×"
        ),
        _box_line(f"Why    {why}"),
        "└" + "─" * 62 + "┘",
    ]
    return "\n".join(lines)


def format_miss(result: EdgeResult, *, team: str) -> str:
    return (
        f"  FAIL  {team} {result.side.upper()} @ {result.price:.2f}  "
        f"netEV {result.net_ev:+.1%}  {result.reason}"
    )


def format_rank_table(rows: list[tuple[EdgeResult, str, str]]) -> str:
    if not rows:
        return "ranked: (empty)"
    lines = [f"ranked: {len(rows)} evaluated  (PASS only boxed below)"]
    for result, team, _why in rows[:12]:
        lines.append(
            f"  {result.verdict:<4} {team:<16} {result.side.upper()} @ {result.price:.2f}  "
            f"netEV {result.net_ev:+.1%}  {result.source_of_fair}"
        )
    return "\n".join(lines)


def print_slate(rows: list[tuple[EdgeResult, str, str]]) -> None:
    """rows: (result, team, why)."""
    ranked = sorted(rows, key=lambda item: item[0].net_ev, reverse=True)
    if ranked:
        print(format_rank_table(ranked))
        print()
    passes = [(result, team, why) for result, team, why in ranked if result.passed]
    misses = [(result, team, why) for result, team, why in ranked if not result.passed]
    if passes:
        for result, team, why in passes:
            print(format_pass(result, team=team, why=why))
            print()
        return
    print("No actionable edge")
    print()
    if misses:
        print("Closest misses:")
        for result, team, _why in misses[:8]:
            print(format_miss(result, team=team))
