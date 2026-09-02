"""Standings / pythag fallback. Tagged low_confidence. Never the live trigger."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from mlbkalshi.names import team_code

STANDINGS_URL = "https://statsapi.mlb.com/api/v1/standings?leagueId=103,104"
TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"


@dataclass(frozen=True)
class ModelFair:
    code: str
    win_pct: float
    pythag: float | None
    source: str = "standings"


def _get(url: str) -> dict:
    with httpx.Client(timeout=20.0, headers={"User-Agent": "mlbkalshi/0.1"}) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.json()


def load_model_fairs() -> dict[str, ModelFair]:
    teams = _get(TEAMS_URL)
    by_id: dict[int, str] = {}
    for team in teams.get("teams") or []:
        code = team_code(team.get("abbreviation") or "") or (team.get("abbreviation") or "").upper()
        if team.get("id") and code:
            by_id[int(team["id"])] = code
    standings = _get(STANDINGS_URL)
    out: dict[str, ModelFair] = {}
    for block in standings.get("records") or []:
        for rec in block.get("teamRecords") or []:
            team_id = (rec.get("team") or {}).get("id")
            code = by_id.get(int(team_id)) if team_id is not None else None
            if not code:
                continue
            scored = float(rec.get("runsScored") or 0)
            allowed = float(rec.get("runsAllowed") or 0)
            pythag = None
            if scored > 0 and allowed > 0:
                pythag = (scored**2) / (scored**2 + allowed**2)
            out[code] = ModelFair(
                code=code,
                win_pct=float(rec.get("winningPercentage") or 0),
                pythag=pythag,
                source="standings+pythag" if pythag is not None else "standings",
            )
    return out


def model_win_prob(code: str, models: dict[str, ModelFair]) -> float | None:
    row = models.get(code)
    if row is None:
        return None
    if row.pythag is None:
        return row.win_pct
    return (row.win_pct + row.pythag) / 2
