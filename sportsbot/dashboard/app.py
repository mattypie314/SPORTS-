from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sportsbot.config import Settings
from sportsbot.paper import PaperBook
from sportsbot.service import scan_board, serialize_board

STATIC_DIR = Path(__file__).parent / "static"


@lru_cache(maxsize=1)
def _settings_from_env() -> Settings:
    return Settings()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or _settings_from_env()
    app = FastAPI(title="Kalshi MLB Bot", version="0.1.0")
    book = PaperBook(settings)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "mode": "paper", "league": "mlb"}

    @app.get("/api/board")
    def board() -> dict:
        events, signals = scan_board(settings)
        return serialize_board(events, signals)

    @app.get("/api/paper")
    def paper_status() -> dict:
        return book.status()

    @app.post("/api/paper/trade")
    def paper_trade() -> dict:
        events, signals = scan_board(settings)
        actionable = [signal for signal in signals if signal.kind in {"arb_buy", "arb_sell", "sportsbook_value"}]
        fills = book.execute_actionable(actionable, events)
        return {
            "fills": [fill.to_dict() for fill in fills],
            "status": book.status(),
            "signals": [signal.to_dict() for signal in signals],
        }

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(STATIC_DIR / "index.html")

    return app
