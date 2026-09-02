from __future__ import annotations

import uuid

from sportsbot.config import Settings
from sportsbot.kalshi.client import KalshiClient
from sportsbot.kalshi.models import EventMarkets
from sportsbot.risk import RiskBlocked, RiskManager
from sportsbot.signals import Signal


class LiveTradingDisabled(RuntimeError):
    pass


def require_live(settings: Settings) -> None:
    if not settings.live_enabled:
        raise LiveTradingDisabled("Set KALSHI_ENABLE_LIVE=true to send real orders")
    if not settings.kalshi_api_key_id or not settings.kalshi_private_key_path:
        raise LiveTradingDisabled("KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH are required")


def place_signal_orders(
    settings: Settings,
    signal: Signal,
    events: list[EventMarkets],
    client: KalshiClient | None = None,
) -> list[dict]:
    require_live(settings)
    if signal.kind not in {"arb_buy", "sportsbook_value"}:
        raise LiveTradingDisabled(f"Refusing to live-trade signal kind {signal.kind}")
    event = next((item for item in events if item.event_ticker == signal.event_ticker), None)
    if event is None:
        return []
    risk = RiskManager(settings)
    owns = client is None
    client = client or KalshiClient(
        settings.kalshi_trade_url,
        timeout=settings.request_timeout,
        api_key_id=settings.kalshi_api_key_id,
        private_key_path=settings.kalshi_private_key_path,
    )
    try:
        orders: list[dict] = []
        markets = {market.ticker: market for market in event.markets}
        legs: list[tuple[str, float]] = []
        for ticker in signal.tickers:
            market = markets[ticker]
            if market.yes_ask is None:
                continue
            legs.append((ticker, market.yes_ask))
        if not legs:
            return []
        basket = sum(price for _, price in legs)
        contracts = risk.size_for_price(basket)
        risk.check_entry(notional=round(contracts * basket, 2), open_positions=0, spent_today=0.0)
        for ticker, price in legs:
            payload = {
                "ticker": ticker,
                "side": "bid",
                "count": f"{contracts:.2f}",
                "price": f"{price:.4f}",
                "time_in_force": "immediate_or_cancel",
                "self_trade_prevention_type": "taker_at_cross",
                "client_order_id": str(uuid.uuid4()),
            }
            orders.append(client.create_order(payload))
        return orders
    except RiskBlocked:
        return []
    finally:
        if owns:
            client.close()
