from __future__ import annotations

import base64
import time
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


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
