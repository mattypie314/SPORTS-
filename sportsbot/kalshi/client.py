from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

import httpx
from cryptography.hazmat.primitives.asymmetric import rsa

from sportsbot.kalshi.auth import auth_headers, load_private_key


class KalshiError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Kalshi API {status_code}: {body}")
        self.status_code = status_code
        self.body = body


class KalshiClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 20.0,
        api_key_id: str = "",
        private_key_path: str = "",
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout
        self.api_key_id = api_key_id
        self._private_key: rsa.RSAPrivateKey | None = None
        if private_key_path:
            self._private_key = load_private_key(private_key_path)
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=timeout, headers={"User-Agent": "sportsbot/0.1"})

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> KalshiClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        signed: bool = False,
    ) -> Any:
        url = self._url(path)
        headers: dict[str, str] = {}
        if signed:
            if not self.api_key_id or self._private_key is None:
                raise RuntimeError("Kalshi API key id and private key are required for signed requests")
            headers.update(auth_headers(self.api_key_id, self._private_key, method, url))
        response = self._client.request(method, url, params=params, json=json, headers=headers)
        if response.status_code >= 400:
            raise KalshiError(response.status_code, response.text)
        if not response.content:
            return None
        return response.json()

    def get(self, path: str, params: dict[str, Any] | None = None, signed: bool = False) -> Any:
        return self.request("GET", path, params=params, signed=signed)

    def paginate(
        self,
        path: str,
        key: str,
        params: dict[str, Any] | None = None,
        signed: bool = False,
        max_pages: int = 20,
    ) -> list[Any]:
        items: list[Any] = []
        cursor: str | None = None
        query = dict(params or {})
        for _ in range(max_pages):
            if cursor:
                query["cursor"] = cursor
            payload = self.get(path, params=query, signed=signed)
            page = payload.get(key) or []
            items.extend(page)
            cursor = payload.get("cursor") or None
            if not cursor or not page:
                break
        return items

    def list_events(
        self,
        *,
        series_ticker: str,
        status: str = "open",
        with_nested_markets: bool = True,
        limit: int = 200,
        max_pages: int = 10,
    ) -> list[dict]:
        params: dict[str, Any] = {
            "series_ticker": series_ticker,
            "with_nested_markets": str(with_nested_markets).lower(),
            "limit": limit,
        }
        if status:
            params["status"] = status
        return self.paginate("events", "events", params=params, max_pages=max_pages)

    def get_balance(self) -> dict:
        return self.get("portfolio/balance", signed=True)

    def create_order(self, order: dict) -> dict:
        return self.request("POST", "portfolio/events/orders", json=order, signed=True)
