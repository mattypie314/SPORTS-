"""Signed Kalshi portfolio (read-only) and Create Order behind LIVE_TRADING=1.

RSA-PSS per Kalshi docs. Never log private keys. Settlement is Kalshi contract
language — unplayed playoff Game 5/6/7 typically marks to last fair, not a
sportsbook void.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from mlbkalshi.config import Settings

PROD = "https://external-api.kalshi.com/trade-api/v2"
DEMO = "https://demo-api.kalshi.co/trade-api/v2"


class LiveDisabled(RuntimeError):
    pass


class KalshiSignedError(RuntimeError):
    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Kalshi signed API {status_code}: {body}")
        self.status_code = status_code
        self.body = body


def load_private_key(path: str | Path) -> rsa.RSAPrivateKey:
    pem = Path(path).read_bytes()
    key = serialization.load_pem_private_key(pem, password=None, backend=default_backend())
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError("Kalshi private key must be an RSA key")
    return key


def sign_request(private_key: rsa.RSAPrivateKey, timestamp_ms: str, method: str, path: str) -> str:
    message = f"{timestamp_ms}{method.upper()}{path}".encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def auth_headers(api_key_id: str, private_key: rsa.RSAPrivateKey, method: str, url: str) -> dict[str, str]:
    timestamp_ms = str(int(time.time() * 1000))
    path = urlparse(url).path
    return {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
        "KALSHI-ACCESS-SIGNATURE": sign_request(private_key, timestamp_ms, method, path),
    }


def looks_like_optional_playoff_game(title: str) -> bool:
    text = (title or "").lower()
    return any(token in text for token in ("game 5", "game 6", "game 7", "gm5", "gm6", "gm7"))


class KalshiSigned:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.has_keys:
            raise LiveDisabled("KALSHI_API_KEY_ID and KALSHI_PRIVATE_KEY_PATH are required")
        self.settings = settings
        self.base_url = (DEMO if settings.kalshi_env.lower() == "demo" else PROD).rstrip("/") + "/"
        self._key = load_private_key(settings.kalshi_private_key_path)
        self._owns = client is None
        self._client = client or httpx.Client(timeout=20.0, headers={"User-Agent": "mlbkalshi/0.1"})

    def close(self) -> None:
        if self._owns:
            self._client.close()

    def __enter__(self) -> KalshiSigned:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        url = urljoin(self.base_url, path.lstrip("/"))
        headers = auth_headers(self.settings.kalshi_key_id, self._key, method, url)
        response = self._client.request(method, url, json=json, headers=headers)
        if response.status_code >= 400:
            raise KalshiSignedError(response.status_code, response.text)
        if not response.content:
            return None
        return response.json()

    def balance(self) -> dict:
        return self.request("GET", "portfolio/balance")

    def positions(self) -> dict | list:
        return self.request("GET", "portfolio/positions")

    def create_order(self, order: dict[str, Any]) -> dict:
        if not self.settings.live_allowed:
            raise LiveDisabled("Create Order requires LIVE_TRADING=1 and API keys")
        return self.request("POST", "portfolio/orders", json=order)


def place_limit_yes(
    settings: Settings,
    *,
    ticker: str,
    price: float,
    contracts: int,
    client: httpx.Client | None = None,
) -> dict:
    """Buy Yes as a limit/maker. Disabled unless LIVE_TRADING=1."""
    if not settings.live_allowed:
        raise LiveDisabled("Create Order requires LIVE_TRADING=1 and API keys")
    cents = max(1, min(99, int(round(price * 100))))
    payload = {
        "ticker": ticker,
        "client_order_id": f"mlbkalshi-{int(time.time())}",
        "side": "yes",
        "action": "buy",
        "count": int(contracts),
        "type": "limit",
        "yes_price": cents,
    }
    with KalshiSigned(settings, client=client) as api:
        return api.create_order(payload)
