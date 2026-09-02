from __future__ import annotations

from dataclasses import dataclass, field

from sportsbot.kalshi.models import EventMarkets, GameMarket


@dataclass(frozen=True)
class Signal:
    kind: str
    league: str
    league_label: str
    event_ticker: str
    title: str
    subtitle: str
    edge: float
    summary: str
    tickers: list[str]
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "league": self.league,
            "league_label": self.league_label,
            "event_ticker": self.event_ticker,
            "title": self.title,
            "subtitle": self.subtitle,
            "edge": round(self.edge, 4),
            "summary": self.summary,
            "tickers": self.tickers,
            "details": self.details,
        }


def complementary_buy_arb(event: EventMarkets, min_edge: float, min_volume: float) -> Signal | None:
    """Buy YES on every mutually exclusive outcome when the asks sum to less than $1."""
    if len(event.markets) < 2:
        return None
    asks: list[float] = []
    for market in event.markets:
        if market.yes_ask is None or market.volume < min_volume:
            return None
        asks.append(market.yes_ask)
    cost = sum(asks)
    edge = 1.0 - cost
    if edge < min_edge:
        return None
    legs = ", ".join(f"{market.team} @{market.yes_ask:.2f}" for market in event.markets)
    return Signal(
        kind="arb_buy",
        league=event.league,
        league_label=event.league_label,
        event_ticker=event.event_ticker,
        title=event.title,
        subtitle=event.subtitle,
        edge=edge,
        summary=f"Buy all YES legs for ${cost:.2f} (edge {edge:.1%}): {legs}",
        tickers=[market.ticker for market in event.markets],
        details={
            "cost": round(cost, 4),
            "asks": {market.ticker: market.yes_ask for market in event.markets},
            "side": "bid",
        },
    )


def complementary_sell_arb(event: EventMarkets, min_edge: float, min_volume: float) -> Signal | None:
    """Sell YES on every mutually exclusive outcome when the bids sum to more than $1."""
    if len(event.markets) < 2:
        return None
    bids: list[float] = []
    for market in event.markets:
        if market.yes_bid is None or market.volume < min_volume:
            return None
        bids.append(market.yes_bid)
    proceeds = sum(bids)
    edge = proceeds - 1.0
    if edge < min_edge:
        return None
    legs = ", ".join(f"{market.team} @{market.yes_bid:.2f}" for market in event.markets)
    return Signal(
        kind="arb_sell",
        league=event.league,
        league_label=event.league_label,
        event_ticker=event.event_ticker,
        title=event.title,
        subtitle=event.subtitle,
        edge=edge,
        summary=f"Sell all YES legs for ${proceeds:.2f} (edge {edge:.1%}): {legs}",
        tickers=[market.ticker for market in event.markets],
        details={
            "proceeds": round(proceeds, 4),
            "bids": {market.ticker: market.yes_bid for market in event.markets},
            "side": "ask",
        },
    )


def wide_spread_signal(market: GameMarket, event: EventMarkets, wide_spread: float) -> Signal | None:
    if market.spread is None or market.spread < wide_spread:
        return None
    return Signal(
        kind="wide_spread",
        league=event.league,
        league_label=event.league_label,
        event_ticker=event.event_ticker,
        title=event.title,
        subtitle=market.team,
        edge=market.spread,
        summary=f"{market.team} book is {market.spread:.0%} wide ({market.yes_bid:.2f}–{market.yes_ask:.2f})",
        tickers=[market.ticker],
        details={"yes_bid": market.yes_bid, "yes_ask": market.yes_ask, "spread": market.spread},
    )


def move_signal(market: GameMarket, event: EventMarkets, min_move: float = 0.04) -> Signal | None:
    if market.last_price is None or market.previous_price is None or market.previous_price <= 0:
        return None
    change = market.last_price - market.previous_price
    if abs(change) < min_move:
        return None
    direction = "up" if change > 0 else "down"
    return Signal(
        kind="price_move",
        league=event.league,
        league_label=event.league_label,
        event_ticker=event.event_ticker,
        title=event.title,
        subtitle=market.team,
        edge=abs(change),
        summary=f"{market.team} last {direction} {change:+.0%} to {market.last_price:.2f}",
        tickers=[market.ticker],
        details={
            "last_price": market.last_price,
            "previous_price": market.previous_price,
            "change": round(change, 4),
        },
    )


def sportsbook_value_signal(
    market: GameMarket,
    event: EventMarkets,
    fair_prob: float,
    min_edge: float,
) -> Signal | None:
    if market.yes_ask is None:
        return None
    edge = fair_prob - market.yes_ask
    if edge < min_edge:
        return None
    return Signal(
        kind="sportsbook_value",
        league=event.league,
        league_label=event.league_label,
        event_ticker=event.event_ticker,
        title=event.title,
        subtitle=market.team,
        edge=edge,
        summary=(
            f"{market.team} Kalshi ask {market.yes_ask:.2f} vs vig-free sportsbook "
            f"{fair_prob:.2f} (edge {edge:.1%})"
        ),
        tickers=[market.ticker],
        details={
            "yes_ask": market.yes_ask,
            "fair_prob": round(fair_prob, 4),
            "side": "bid",
            "price": market.yes_ask,
        },
    )


def collect_signals(
    events: list[EventMarkets],
    *,
    min_edge: float,
    min_volume: float,
    wide_spread: float,
    extra: list[Signal] | None = None,
) -> list[Signal]:
    found: list[Signal] = []
    for event in events:
        buy = complementary_buy_arb(event, min_edge=min_edge, min_volume=min_volume)
        if buy:
            found.append(buy)
        sell = complementary_sell_arb(event, min_edge=min_edge, min_volume=min_volume)
        if sell:
            found.append(sell)
        for market in event.markets:
            wide = wide_spread_signal(market, event, wide_spread)
            if wide:
                found.append(wide)
            moved = move_signal(market, event)
            if moved:
                found.append(moved)
    if extra:
        found.extend(extra)
    found.sort(key=lambda signal: (-signal.edge, signal.kind, signal.event_ticker))
    return found
