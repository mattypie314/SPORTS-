"""CSV paper ledger, daily idea cap, correlation grouping, drawdown kill."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from mlbkalshi.config import Settings
from mlbkalshi.fees import EdgeResult
from mlbkalshi.names import parse_ticker, teams_from_ticker

LEDGER_FIELDS = (
    "time",
    "ticker",
    "side",
    "entry",
    "fair",
    "source_of_fair",
    "net_ev",
    "contracts",
    "risk",
    "reason",
    "result",
)

DAILY_IDEA_CAP = 3
DRAWDOWN_KILL = 0.25


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def idea_group(ticker: str) -> str:
    """Same pitcher stack / same total lean counts as one daily idea."""
    parsed = parse_ticker(ticker)
    away, home = teams_from_ticker(ticker)
    game = f"{parsed.date or '?'}:{away or '?'}:{home or '?'}"
    if parsed.series == "KXMLBTOTAL":
        return f"{game}:total"
    if parsed.series == "KXMLBRFI":
        return f"{game}:rfi"
    return f"{game}:stack"


@dataclass(frozen=True)
class PaperRow:
    time: str
    ticker: str
    side: str
    entry: float
    fair: float
    source_of_fair: str
    net_ev: float
    contracts: float
    risk: float
    reason: str
    result: str

    def as_dict(self) -> dict[str, str]:
        return {
            "time": self.time,
            "ticker": self.ticker,
            "side": self.side,
            "entry": f"{self.entry:.4f}",
            "fair": f"{self.fair:.4f}",
            "source_of_fair": self.source_of_fair,
            "net_ev": f"{self.net_ev:.4f}",
            "contracts": f"{self.contracts:.2f}",
            "risk": f"{self.risk:.2f}",
            "reason": self.reason,
            "result": self.result,
        }


class PaperBlocked(RuntimeError):
    pass


class PaperLedger:
    def __init__(self, settings: Settings, path: str | Path | None = None) -> None:
        self.settings = settings
        root = Path(settings.data_dir)
        root.mkdir(parents=True, exist_ok=True)
        self.path = Path(path) if path else root / "mlbkalshi_ledger.csv"
        self.account_path = root / "mlbkalshi_account.json"
        self._ensure()

    def _ensure(self) -> None:
        if not self.path.exists():
            with self.path.open("w", newline="") as handle:
                csv.DictWriter(handle, fieldnames=LEDGER_FIELDS).writeheader()
        if not self.account_path.exists():
            self._write_account(
                {
                    "cash": self.settings.bankroll,
                    "peak": self.settings.bankroll,
                    "kill": False,
                    "starting": self.settings.bankroll,
                }
            )

    def _read_account(self) -> dict:
        return json.loads(self.account_path.read_text())

    def _write_account(self, payload: dict) -> None:
        self.account_path.write_text(json.dumps(payload, indent=2) + "\n")

    def rows(self) -> list[PaperRow]:
        if not self.path.exists():
            return []
        with self.path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            out: list[PaperRow] = []
            for row in reader:
                out.append(
                    PaperRow(
                        time=row["time"],
                        ticker=row["ticker"],
                        side=row["side"],
                        entry=float(row["entry"]),
                        fair=float(row["fair"]),
                        source_of_fair=row["source_of_fair"],
                        net_ev=float(row["net_ev"]),
                        contracts=float(row["contracts"]),
                        risk=float(row["risk"]),
                        reason=row.get("reason") or "",
                        result=row.get("result") or "open",
                    )
                )
            return out

    def cash(self) -> float:
        return float(self._read_account()["cash"])

    def killed(self) -> bool:
        account = self._read_account()
        return bool(account.get("kill"))

    def reset_kill(self) -> None:
        account = self._read_account()
        account["kill"] = False
        account["peak"] = float(account["cash"])
        self._write_account(account)

    def _touch_drawdown(self, account: dict) -> dict:
        cash = float(account["cash"])
        peak = max(float(account.get("peak") or cash), cash)
        account["peak"] = peak
        if peak > 0 and (peak - cash) / peak >= DRAWDOWN_KILL:
            account["kill"] = True
        return account

    def ideas_today(self) -> set[str]:
        today = _today()
        groups: set[str] = set()
        for row in self.rows():
            if row.time.startswith(today):
                groups.add(idea_group(row.ticker))
        return groups

    def record(self, ticker: str, result: EdgeResult, *, why: str = "") -> PaperRow:
        account = self._read_account()
        account = self._touch_drawdown(account)
        if account.get("kill"):
            raise PaperBlocked("kill switch: drawdown ≥ 25% from peak — reset before new papers")
        group = idea_group(ticker)
        today_groups = self.ideas_today()
        new_idea = group not in today_groups
        if new_idea and len(today_groups) >= DAILY_IDEA_CAP:
            raise PaperBlocked(f"daily idea cap ({DAILY_IDEA_CAP}) reached")
        risk = float(result.size.risk)
        if risk > float(account["cash"]) + 1e-9:
            raise PaperBlocked("insufficient paper cash")
        account["cash"] = round(float(account["cash"]) - risk, 2)
        account = self._touch_drawdown(account)
        self._write_account(account)
        row = PaperRow(
            time=_utc_now(),
            ticker=ticker,
            side=result.side,
            entry=result.price,
            fair=result.fair,
            source_of_fair=result.source_of_fair,
            net_ev=result.net_ev,
            contracts=result.size.contracts,
            risk=risk,
            reason=why or result.reason,
            result="open",
        )
        with self.path.open("a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
            writer.writerow(row.as_dict())
        return row

    def settle(self, ticker: str, result: str) -> PaperRow:
        """Mark the newest open row for ticker. win/lose/void (Kalshi language)."""
        result = result.lower()
        if result not in {"win", "lose", "void"}:
            raise ValueError("result must be win, lose, or void")
        rows = self.rows()
        idx = next((i for i in range(len(rows) - 1, -1, -1) if rows[i].ticker == ticker and rows[i].result == "open"), None)
        if idx is None:
            raise PaperBlocked(f"no open paper for {ticker}")
        current = rows[idx]
        account = self._read_account()
        cash = float(account["cash"])
        if result == "win":
            cash += current.contracts
        elif result == "void":
            cash += current.risk
        account["cash"] = round(cash, 2)
        account = self._touch_drawdown(account)
        self._write_account(account)
        updated = PaperRow(**{**current.__dict__, "result": result})
        rows[idx] = updated
        with self.path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow(row.as_dict())
        return updated

    def status(self) -> dict:
        account = self._touch_drawdown(self._read_account())
        self._write_account(account)
        return {
            "mode": "paper",
            "cash": round(float(account["cash"]), 2),
            "peak": round(float(account["peak"]), 2),
            "kill": bool(account.get("kill")),
            "ideas_today": sorted(self.ideas_today()),
            "ideas_today_count": len(self.ideas_today()),
            "daily_cap": DAILY_IDEA_CAP,
            "rows": [row.as_dict() for row in self.rows()],
        }
