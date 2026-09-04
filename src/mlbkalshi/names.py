"""Kalshi MLB labels ↔ official team codes."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Official MLB abbreviations (Stats API).
TEAMS: dict[str, dict[str, str]] = {
    "AZ": {"name": "Arizona Diamondbacks", "nick": "D-backs", "city": "Arizona"},
    "ATL": {"name": "Atlanta Braves", "nick": "Braves", "city": "Atlanta"},
    "BAL": {"name": "Baltimore Orioles", "nick": "Orioles", "city": "Baltimore"},
    "BOS": {"name": "Boston Red Sox", "nick": "Red Sox", "city": "Boston"},
    "CHC": {"name": "Chicago Cubs", "nick": "Cubs", "city": "Chicago"},
    "CWS": {"name": "Chicago White Sox", "nick": "White Sox", "city": "Chicago"},
    "CIN": {"name": "Cincinnati Reds", "nick": "Reds", "city": "Cincinnati"},
    "CLE": {"name": "Cleveland Guardians", "nick": "Guardians", "city": "Cleveland"},
    "COL": {"name": "Colorado Rockies", "nick": "Rockies", "city": "Colorado"},
    "DET": {"name": "Detroit Tigers", "nick": "Tigers", "city": "Detroit"},
    "HOU": {"name": "Houston Astros", "nick": "Astros", "city": "Houston"},
    "KC": {"name": "Kansas City Royals", "nick": "Royals", "city": "Kansas City"},
    "LAA": {"name": "Los Angeles Angels", "nick": "Angels", "city": "Los Angeles"},
    "LAD": {"name": "Los Angeles Dodgers", "nick": "Dodgers", "city": "Los Angeles"},
    "MIA": {"name": "Miami Marlins", "nick": "Marlins", "city": "Miami"},
    "MIL": {"name": "Milwaukee Brewers", "nick": "Brewers", "city": "Milwaukee"},
    "MIN": {"name": "Minnesota Twins", "nick": "Twins", "city": "Minnesota"},
    "NYM": {"name": "New York Mets", "nick": "Mets", "city": "New York"},
    "NYY": {"name": "New York Yankees", "nick": "Yankees", "city": "New York"},
    "ATH": {"name": "Athletics", "nick": "Athletics", "city": "Sacramento"},
    "PHI": {"name": "Philadelphia Phillies", "nick": "Phillies", "city": "Philadelphia"},
    "PIT": {"name": "Pittsburgh Pirates", "nick": "Pirates", "city": "Pittsburgh"},
    "SD": {"name": "San Diego Padres", "nick": "Padres", "city": "San Diego"},
    "SF": {"name": "San Francisco Giants", "nick": "Giants", "city": "San Francisco"},
    "SEA": {"name": "Seattle Mariners", "nick": "Mariners", "city": "Seattle"},
    "STL": {"name": "St. Louis Cardinals", "nick": "Cardinals", "city": "St. Louis"},
    "TB": {"name": "Tampa Bay Rays", "nick": "Rays", "city": "Tampa Bay"},
    "TEX": {"name": "Texas Rangers", "nick": "Rangers", "city": "Texas"},
    "TOR": {"name": "Toronto Blue Jays", "nick": "Blue Jays", "city": "Toronto"},
    "WSH": {"name": "Washington Nationals", "nick": "Nationals", "city": "Washington"},
}

# Kalshi-specific and book-specific aliases. Longer keys win.
ALIASES: dict[str, str] = {
    "a's": "ATH",
    "as": "ATH",
    "athletics": "ATH",
    "oakland": "ATH",
    "oakland athletics": "ATH",
    "sacramento": "ATH",
    "sacramento athletics": "ATH",
    "oak": "ATH",
    "new york y": "NYY",
    "new york yankees": "NYY",
    "yankees": "NYY",
    "nyy": "NYY",
    "new york m": "NYM",
    "new york mets": "NYM",
    "mets": "NYM",
    "nym": "NYM",
    "chicago c": "CHC",
    "chicago cubs": "CHC",
    "cubs": "CHC",
    "chc": "CHC",
    "chi cubs": "CHC",
    "chicago ws": "CWS",
    "chicago w": "CWS",
    "chicago white sox": "CWS",
    "white sox": "CWS",
    "cws": "CWS",
    "chw": "CWS",
    "chi sox": "CWS",
    "los angeles d": "LAD",
    "los angeles dodgers": "LAD",
    "dodgers": "LAD",
    "lad": "LAD",
    "la dodgers": "LAD",
    "los angeles a": "LAA",
    "los angeles r": "LAA",
    "los angeles angels": "LAA",
    "angels": "LAA",
    "laa": "LAA",
    "la angels": "LAA",
    "anaheim": "LAA",
    "d-backs": "AZ",
    "dbacks": "AZ",
    "diamondbacks": "AZ",
    "arizona": "AZ",
    "arizona diamondbacks": "AZ",
    "ari": "AZ",
    "az": "AZ",
    "st. louis": "STL",
    "st louis": "STL",
    "saint louis": "STL",
    "cardinals": "STL",
    "washington nationals": "WSH",
    "nationals": "WSH",
    "was": "WSH",
    "wsh": "WSH",
    "san diego": "SD",
    "padres": "SD",
    "sdp": "SD",
    "san francisco": "SF",
    "giants": "SF",
    "sfg": "SF",
    "kansas city": "KC",
    "royals": "KC",
    "kcr": "KC",
    "tampa bay": "TB",
    "rays": "TB",
    "tbr": "TB",
}


@dataclass(frozen=True)
class ParsedTicker:
    series: str
    date: str | None
    outcome: str | None
    raw: str


_TICKER_RE = re.compile(
    r"^(?P<series>KX[A-Z0-9]+)-(?P<body>.+)$",
    re.IGNORECASE,
)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def team_code(label: str) -> str | None:
    raw = (label or "").strip()
    if not raw:
        return None
    key = raw.upper()
    if key in TEAMS:
        return key
    norm = normalize(raw)
    alias_norm = {normalize(alias): code for alias, code in ALIASES.items()}
    if norm in alias_norm:
        return alias_norm[norm]
    padded = f" {norm} "
    hits = [
        (alias, code)
        for alias, code in alias_norm.items()
        if len(alias) >= 4 and f" {alias} " in padded
    ]
    if hits:
        hits.sort(key=lambda item: len(item[0]), reverse=True)
        return hits[0][1]
    for code, meta in TEAMS.items():
        for value in meta.values():
            if normalize(value) == norm:
                return code
            if len(norm) > 4 and norm in normalize(value).split():
                return code
    return None


def parse_ticker(ticker: str) -> ParsedTicker:
    raw = ticker.strip()
    match = _TICKER_RE.match(raw)
    if not match:
        return ParsedTicker(series="", date=None, outcome=None, raw=raw)
    series = match.group("series").upper()
    body = match.group("body")
    outcome = None
    if "-" in body:
        body, outcome = body.rsplit("-", 1)
    date = None
    date_match = re.match(r"^(?P<date>\d{2}[A-Z]{3}\d{2})", body, re.IGNORECASE)
    if date_match:
        date = date_match.group("date").upper()
    return ParsedTicker(series=series, date=date, outcome=outcome, raw=raw)


_MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


def parse_kalshi_date(token: str):
    """Convert a Kalshi date token like 26SEP02 to datetime.date."""
    from datetime import date

    raw = (token or "").strip().upper()
    match = re.fullmatch(r"(\d{2})([A-Z]{3})(\d{2})", raw)
    if not match:
        return None
    year = 2000 + int(match.group(1))
    month = _MONTHS.get(match.group(2))
    day = int(match.group(3))
    if month is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def event_date_from_ticker(ticker: str):
    return parse_kalshi_date(parse_ticker(ticker).date or "")


def team_code_from_text(text: str) -> str | None:
    """Resolve a team from a full Kalshi title ('Colorado wins by over 1.5')."""
    direct = team_code(text)
    if direct:
        return direct
    words = normalize(text).split()
    for n in range(min(4, len(words)), 0, -1):
        hit = team_code(" ".join(words[:n]))
        if hit:
            return hit
    return None


def codes_from_event_title(title: str) -> tuple[str | None, str | None]:
    """Parse 'Away vs Home' style Kalshi titles, including ': Spread' suffixes."""
    cleaned = re.sub(r":\s*.+$", "", title or "").strip()
    parts = re.split(r"\s+vs\.?\s+", cleaned, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) != 2:
        return None, None
    return team_code(parts[0]), team_code(parts[1])


def teams_from_ticker(ticker: str) -> tuple[str | None, str | None]:
    """Read away/home codes from a Kalshi ticker body (ATLWSH, 1305ATLWSH)."""
    parsed = parse_ticker(ticker)
    body = parsed.raw
    match = _TICKER_RE.match(body)
    if not match:
        return None, None
    rest = match.group("body")
    if parsed.outcome and rest.endswith(f"-{parsed.outcome}"):
        rest = rest[: -(len(parsed.outcome) + 1)]
    rest = re.sub(r"^\d{2}[A-Z]{3}\d{2}", "", rest, flags=re.IGNORECASE)
    rest = re.sub(r"^\d{4}", "", rest)
    rest = rest.upper()
    codes = sorted(TEAMS, key=len, reverse=True)
    for away in codes:
        if rest.startswith(away):
            home = rest[len(away) :]
            if home in TEAMS:
                return away, home
    return None, None
