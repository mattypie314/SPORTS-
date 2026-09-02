"""Kalshi quadratic fees, EV, Kelly, and the PASS/FAIL gate."""

from __future__ import annotations

from dataclasses import dataclass, field

TAKER_RATE = 0.07
MAKER_RATE = 0.0175
DEFAULT_KELLY = 0.30
DEFAULT_RISK_CAP = 0.06
PASS_EV = 0.06
TIGHT_EV = 0.04
LOW_CONF_EV = 0.10
EXTREME_EV = 0.10
FAVORITE_CUTOFF = 0.80
LONGSHOT_CUTOFF = 0.15


@dataclass(frozen=True)
class Size:
    contracts: float
    risk: float
    kelly_full: float
    kelly_used: float


@dataclass(frozen=True)
class EdgeResult:
    side: str
    price: float
    fair: float
    fee: float
    maker: bool
    gross_ev: float
    net_ev: float
    size: Size
    passed: bool
    reason: str
    source_of_fair: str = "book"
    disagree_pts: float = 0.0
    extras: dict = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        return "PASS" if self.passed else "FAIL"


def fee_per_contract(price: float, *, maker: bool = False, multiplier: float = 1.0) -> float:
    if price <= 0 or price >= 1:
        return 0.0
    rate = MAKER_RATE if maker else TAKER_RATE
    return multiplier * rate * price * (1.0 - price)


def gross_ev(fair: float, price: float) -> float:
    return fair - price


def net_ev(fair: float, price: float, *, maker: bool = False, multiplier: float = 1.0) -> float:
    return gross_ev(fair, price) - fee_per_contract(price, maker=maker, multiplier=multiplier)


def kelly_full(fair: float, price: float) -> float:
    """Full Kelly as a fraction of bankroll for buying Yes at `price`."""
    if price <= 0 or price >= 1:
        return 0.0
    return max((fair - price) / (1.0 - price), 0.0)


def size_trade(
    fair: float,
    price: float,
    bankroll: float,
    *,
    maker: bool = False,
    kelly_fraction: float = DEFAULT_KELLY,
    risk_cap: float = DEFAULT_RISK_CAP,
) -> Size:
    full = kelly_full(fair, price)
    used = max(min(kelly_fraction, 0.35), 0.25)
    stake = bankroll * full * used
    stake = min(stake, bankroll * risk_cap)
    stake = max(stake, 0.0)
    contracts = 0.0 if price <= 0 else round(stake / price, 2)
    return Size(contracts=contracts, risk=round(stake, 2), kelly_full=full, kelly_used=used)


def ev_gate(
    *,
    price: float,
    net: float,
    spread: float | None,
    disagree_pts: float,
    low_confidence: bool,
) -> tuple[bool, str]:
    extreme = price >= FAVORITE_CUTOFF or price <= LONGSHOT_CUTOFF
    if extreme and low_confidence:
        return False, "skip 80¢+ / 15¢ without a deep book"
    if low_confidence:
        if net >= LOW_CONF_EV:
            return True, "low_confidence but net EV ≥ 10%"
        return False, "low_confidence: need net EV ≥ 10%"
    if extreme:
        if net >= EXTREME_EV:
            return True, "extreme price but net EV ≥ 10%"
        return False, "skip 80¢+ favorite / 15¢ longshot unless net EV ≥ 10%"
    if disagree_pts > 4.0:
        if net >= 0.08:
            return True, "books disagree >4 pts; cleared raised 8% gate"
        return False, "books disagree >4 pts; EV gate raised to 8%"
    tight = disagree_pts <= 2.0 and spread is not None and 0.009 <= spread <= 0.021
    if tight and net >= TIGHT_EV:
        return True, "tight books + 1–2¢ spread; 4% floor"
    if net >= PASS_EV:
        return True, "net EV ≥ 6% after fees"
    return False, "below 6% gate"


def evaluate(
    *,
    fair: float,
    kalshi_yes: float,
    side: str = "yes",
    bankroll: float,
    maker: bool = False,
    spread: float | None = None,
    disagree_pts: float = 0.0,
    source_of_fair: str = "book",
    low_confidence: bool = False,
) -> EdgeResult:
    side = side.lower()
    if side not in {"yes", "no"}:
        raise ValueError("side must be yes or no")
    if side == "yes":
        price = kalshi_yes
        used_fair = fair
    else:
        price = 1.0 - kalshi_yes
        used_fair = 1.0 - fair
    fee = fee_per_contract(price, maker=maker)
    gross = gross_ev(used_fair, price)
    net = gross - fee
    passed, reason = ev_gate(
        price=price,
        net=net,
        spread=spread,
        disagree_pts=disagree_pts,
        low_confidence=low_confidence,
    )
    sized = size_trade(used_fair, price, bankroll, maker=maker)
    if passed and sized.contracts <= 0:
        passed = False
        reason = "edge exists but Kelly/risk cap sizes to 0"
    return EdgeResult(
        side=side,
        price=price,
        fair=used_fair,
        fee=fee,
        maker=maker,
        gross_ev=gross,
        net_ev=net,
        size=sized,
        passed=passed,
        reason=reason,
        source_of_fair=source_of_fair,
        disagree_pts=disagree_pts,
    )
