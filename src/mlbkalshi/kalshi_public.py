"""Paginated public Kalshi Trade API client with 429 backoff."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import urljoin

import httpx

PRODUCTION = "https://external-api.kalshi.com/trade-api/v2"
MLB_SERIES = (
    "KXMLBGAME",
    "KXMLBSPREAD",
    "KXMLBTOTAL",
    "KXMLBRFI",
    "KXMLBF5SPREAD",
)


class KalshiPublicError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Kalshi public API {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class KalshiPublic:
    def __init__(
        self,
        base_url: str = PRODUCTION,
        timeout: float = 20.0,
        client: httpx.Client | None = None,
        max_retries: int = 5,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.max_retries = max_retries
        self._owns = client is None
        self._client = client or httpx.Client(timeout=timeout, headers={"User-Agent": "mlbkalshi/0.1"})

    def close(self) -> None:
        if self._owns:
            self._client.close()

    def __enter__(self) -> KalshiPublic:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        url = urljoin(self.base_url, path.lstrip("/"))
        delay = 0.5
        last_error: Exception | None = None
        for _ in range(self.max_retries):
            response = self._client.get(url, params=params)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else delay
                time.sleep(wait)
                delay = min(delay * 2, 8.0)
                last_error = KalshiPublicError(429, response.text)
                continue
            if response.status_code >= 400:
                raise KalshiPublicError(response.status_code, response.text)
            return response.json()
        raise last_error or KalshiPublicError(429, "rate limited")

    def paginate(self, path: str, key: str, params: dict[str, Any] | None = None, max_pages: int = 15) -> list[Any]:
        items: list[Any] = []
        query = dict(params or {})
        cursor: str | None = None
        for _ in range(max_pages):
            if cursor:
                query["cursor"] = cursor
            payload = self.get(path, params=query)
            page = payload.get(key) or []
            items.extend(page)
            cursor = payload.get("cursor") or None
            if not cursor or not page:
                break
        return items

    def list_events(
        self,
        series_ticker: str,
        *,
        status: str = "open",
        with_nested_markets: bool = True,
        limit: int = 200,
    ) -> list[dict]:
        params: dict[str, Any] = {
            "series_ticker": series_ticker,
            "with_nested_markets": str(with_nested_markets).lower(),
            "limit": limit,
        }
        if status:
            params["status"] = status
        return self.paginate("events", "events", params=params)

    def list_markets(self, series_ticker: str, *, status: str = "open", limit: int = 200) -> list[dict]:
        params: dict[str, Any] = {"series_ticker": series_ticker, "limit": limit}
        if status:
            params["status"] = status
        return self.paginate("markets", "markets", params=params)
