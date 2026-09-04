from pathlib import Path

from fastapi.testclient import TestClient

from sportsbot.config import Settings
from sportsbot.dashboard.app import create_app


def test_health_and_index(tmp_path: Path):
    app = create_app(Settings(data_dir=tmp_path))
    client = TestClient(app)
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert health.json()["league"] == "mlb"
    page = client.get("/")
    assert page.status_code == 200
    assert "Kalshi MLB Bot" in page.text
    assert "NFL" not in page.text


def test_paper_status(tmp_path: Path):
    app = create_app(Settings(data_dir=tmp_path, bankroll=500))
    client = TestClient(app)
    status = client.get("/api/paper").json()
    assert status["cash"] == 500
    assert status["mode"] == "paper"
