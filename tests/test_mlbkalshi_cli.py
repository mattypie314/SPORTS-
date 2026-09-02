from mlbkalshi.cli import build_parser
from mlbkalshi.kalshi_public import KalshiPublic, KalshiPublicError


def test_parser_edge_and_scan():
    parser = build_parser()
    edge = parser.parse_args(["edge", "--book-odds", "-150", "+130", "--kalshi", "0.55", "--side", "yes", "--bankroll", "100"])
    assert edge.command == "edge"
    assert edge.book_odds == [-150, 130]
    scan = parser.parse_args(["scan", "--bankroll", "100"])
    assert scan.command == "scan"
    markets = parser.parse_args(["markets", "--series", "KXMLBGAME"])
    assert markets.series == "KXMLBGAME"


def test_429_retries(monkeypatch):
    class FakeResp:
        def __init__(self, status, payload=None):
            self.status_code = status
            self.text = "slow down"
            self.headers = {}
            self._payload = payload or {}

        def json(self):
            return self._payload

    calls = {"n": 0}

    class FakeClient:
        def get(self, url, params=None):
            calls["n"] += 1
            if calls["n"] < 3:
                return FakeResp(429)
            return FakeResp(200, {"ok": True})

        def close(self):
            return None

    sleeps: list[float] = []
    monkeypatch.setattr("mlbkalshi.kalshi_public.time.sleep", lambda s: sleeps.append(s))
    api = KalshiPublic(client=FakeClient(), max_retries=5)
    assert api.get("markets") == {"ok": True}
    assert calls["n"] == 3
    assert sleeps

    api2 = KalshiPublic(client=FakeClient(), max_retries=1)
    # first call 429 then exhausted
    calls["n"] = 10

    class Always429:
        def get(self, url, params=None):
            return FakeResp(429)

        def close(self):
            return None

    api3 = KalshiPublic(client=Always429(), max_retries=2)
    try:
        api3.get("markets")
        raise AssertionError("expected rate limit error")
    except KalshiPublicError as exc:
        assert exc.status_code == 429
