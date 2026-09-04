"""Phase 0: compare Kalshi MLB moneylines to MLB standings win%."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass

KALSHI = "https://external-api.kalshi.com/trade-api/v2"
MLB_STANDINGS = "https://statsapi.mlb.com/api/v1/standings?leagueId=103,104"
MLB_TEAMS = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
SERIES = "KXMLBGAME"
UA = "mlbkalshi-v0/0.1"

# Kalshi labels that do not match MLB teamName / location.
ALIASES = {
    "a's": "ATH",
    "athletics": "ATH",
    "oakland": "ATH",
    "sacramento": "ATH",
    "new york y": "NYY",
    "new york m": "NYM",
    "chicago c": "CHC",
    "chicago ws": "CWS",
    "chicago w": "CWS",
    "los angeles a": "LAA",
    "los angeles d": "LAD",
    "los angeles r": "LAA",
    "d-backs": "AZ",
    "dbacks": "AZ",
    "diamondbacks": "AZ",
    "arizona": "AZ",
}


@dataclass(frozen=True)
class TeamRow:
    code: str
    name: str
    win_pct: float
    location: str = ""
    nickname: str = ""


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def load_team_catalog() -> dict[int, dict[str, str]]:
    payload = _get(MLB_TEAMS)
    catalog: dict[int, dict[str, str]] = {}
    for team in payload.get("teams") or []:
        team_id = team.get("id")
        code = (team.get("abbreviation") or "").upper()
        if not team_id or not code:
            continue
        catalog[int(team_id)] = {
            "code": code,
            "name": team.get("name") or "",
            "team_name": team.get("teamName") or "",
            "location": team.get("locationName") or "",
        }
    return catalog


def load_standings() -> dict[str, TeamRow]:
    catalog = load_team_catalog()
    payload = _get(MLB_STANDINGS)
    rows: dict[str, TeamRow] = {}
    for block in payload.get("records") or []:
        for rec in block.get("teamRecords") or []:
            team_id = (rec.get("team") or {}).get("id")
            meta = catalog.get(int(team_id)) if team_id is not None else None
            if not meta:
                continue
            pct = float(rec.get("winningPercentage") or 0)
            rows[meta["code"]] = TeamRow(
                code=meta["code"],
                name=meta["name"],
                win_pct=pct,
                location=meta["location"],
                nickname=meta["team_name"],
            )
    return rows


def _catalog_labels(standings: dict[str, TeamRow]) -> dict[str, str]:
    """Best-effort label → code using standings names plus ALIASES."""
    labels: dict[str, str] = {k: v for k, v in ALIASES.items()}
    locations: dict[str, list[str]] = {}
    for code, row in standings.items():
        labels[code.lower()] = code
        labels[row.name.lower()] = code
        if row.nickname:
            labels[row.nickname.lower()] = code
        if row.location:
            locations.setdefault(row.location.lower(), []).append(code)
            labels.setdefault(row.location.lower(), code)
    for loc, codes in locations.items():
        if len(codes) == 1:
            labels[loc] = codes[0]
    return labels


def _dollars(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_code(label: str, standings: dict[str, TeamRow]) -> str | None:
    raw = (label or "").strip()
    if not raw:
        return None
    key = raw.lower()
    if key in ALIASES:
        return ALIASES[key]
    upper = raw.upper()
    if upper in standings:
        return upper
    labels = _catalog_labels(standings)
    if key in labels:
        return labels[key]
    for alias, code in sorted(ALIASES.items(), key=lambda item: -len(item[0])):
        if alias in key:
            return code
    for code, row in standings.items():
        hay = f"{row.name} {code}".lower()
        if key in hay or any(token and token in hay for token in key.split() if len(token) > 3):
            return code
    return None


def list_open_games() -> list[dict]:
    events: list[dict] = []
    cursor = ""
    for _ in range(10):
        url = (
            f"{KALSHI}/events?series_ticker={SERIES}&status=open"
            f"&with_nested_markets=true&limit=200"
        )
        if cursor:
            url += f"&cursor={cursor}"
        try:
            payload = _get(url)
        except urllib.error.HTTPError as exc:
            print(f"kalshi error: {exc}", file=sys.stderr)
            break
        events.extend(payload.get("events") or [])
        cursor = payload.get("cursor") or ""
        if not cursor:
            break
    return events


def main(argv: list[str] | None = None) -> int:
    del argv
    print("v0 standings scanner — low_confidence only, not the live trigger")
    standings = load_standings()
    events = list_open_games()
    print(f"standings teams: {len(standings)}  open KXMLBGAME events: {len(events)}")
    print(f"{'GAME':<36} {'TEAM':<18} {'CODE':<5} {'MID':>6} {'WIN%':>6} {'EDGE':>7}")
    print("-" * 86)
    shown = 0
    for event in events:
        title = event.get("title") or event.get("event_ticker") or ""
        for market in event.get("markets") or []:
            if market.get("status") not in {"active", "open"}:
                continue
            bid = _dollars(market.get("yes_bid_dollars"))
            ask = _dollars(market.get("yes_ask_dollars"))
            if bid is None or ask is None:
                continue
            mid = (bid + ask) / 2
            label = market.get("yes_sub_title") or market.get("title") or ""
            code = resolve_code(label, standings)
            win = standings[code].win_pct if code and code in standings else None
            edge = (win - mid) if win is not None else None
            print(
                f"{title[:36]:<36} {label[:18]:<18} {(code or '?'):<5} "
                f"{mid:6.2f} {((win or 0) if win is not None else 0):6.3f} "
                f"{(edge if edge is not None else 0):+7.3f}"
            )
            shown += 1
    if not shown:
        print("No open MLB moneylines.")
    print("All rows are model_fair / low_confidence. Do not trade on this board.")
    return 0
