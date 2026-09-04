from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from mlbkalshi.config import Settings
from mlbkalshi.live import LiveDisabled, looks_like_optional_playoff_game, place_limit_yes, sign_request


def test_live_order_blocked_without_flag(tmp_path: Path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = tmp_path / "key.pem"
    pem.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    settings = Settings(
        bankroll=100,
        odds_api_key="",
        live_trading=False,
        kalshi_key_id="id",
        kalshi_private_key_path=str(pem),
        books_path="",
        data_dir=str(tmp_path),
        kalshi_env="demo",
    )
    try:
        place_limit_yes(settings, ticker="KXMLBGAME-26SEP02ATLWSH-ATL", price=0.55, contracts=1)
        raise AssertionError("live should be disabled")
    except LiveDisabled:
        pass


def test_sign_request_is_base64():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sig = sign_request(key, "1", "GET", "/trade-api/v2/portfolio/balance")
    assert len(sig) > 20
    assert "BEGIN" not in sig
    assert "PRIVATE" not in sig


def test_playoff_game_language():
    assert looks_like_optional_playoff_game("Yankees vs Guardians Game 5")
    assert not looks_like_optional_playoff_game("Atlanta vs Washington")
