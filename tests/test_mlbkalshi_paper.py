from mlbkalshi.config import Settings
from mlbkalshi.fees import evaluate
from mlbkalshi.paper import DAILY_IDEA_CAP, PaperBlocked, PaperLedger, idea_group


def _settings(tmp_path, bankroll=100.0) -> Settings:
    return Settings(
        bankroll=bankroll,
        odds_api_key="",
        live_trading=False,
        kalshi_key_id="",
        kalshi_private_key_path="",
        books_path="",
        data_dir=str(tmp_path),
        kalshi_env="demo",
    )


def _pass(bankroll=100):
    return evaluate(fair=0.70, kalshi_yes=0.55, side="yes", bankroll=bankroll)


def test_idea_group_correlation():
    assert idea_group("KXMLBGAME-26SEP02ATLWSH-ATL") == idea_group("KXMLBSPREAD-26SEP02ATLWSH-ATL2")
    assert idea_group("KXMLBTOTAL-26SEP02ATLWSH-9") != idea_group("KXMLBGAME-26SEP02ATLWSH-ATL")
    assert idea_group("KXMLBRFI-26SEP02ATLWSH") != idea_group("KXMLBTOTAL-26SEP02ATLWSH-9")


def test_ledger_records_and_settles(tmp_path):
    ledger = PaperLedger(_settings(tmp_path), path=tmp_path / "ledger.csv")
    row = ledger.record("KXMLBGAME-26SEP02ATLWSH-ATL", _pass(), why="test")
    assert row.result == "open"
    assert ledger.cash() < 100
    won = ledger.settle(row.ticker, "win")
    assert won.result == "win"
    assert ledger.cash() > 90


def test_daily_cap_and_correlation(tmp_path):
    ledger = PaperLedger(_settings(tmp_path), path=tmp_path / "ledger.csv")
    ledger.record("KXMLBGAME-26SEP02ATLWSH-ATL", _pass())
    ledger.record("KXMLBSPREAD-26SEP02ATLWSH-ATL2", _pass())  # same stack, not a new idea
    ledger.record("KXMLBGAME-26SEP02NYMTB-NYM", _pass())
    ledger.record("KXMLBGAME-26SEP02SEABOS-SEA", _pass())
    assert len(ledger.ideas_today()) == DAILY_IDEA_CAP
    try:
        ledger.record("KXMLBGAME-26SEP02DETLAD-DET", _pass())
        raise AssertionError("cap should block a fourth idea")
    except PaperBlocked as exc:
        assert "cap" in str(exc)


def test_drawdown_kill(tmp_path):
    ledger = PaperLedger(_settings(tmp_path, bankroll=100), path=tmp_path / "ledger.csv")
    account = ledger._read_account()
    account["cash"] = 70
    account["peak"] = 100
    ledger._write_account(account)
    try:
        ledger.record("KXMLBGAME-26SEP02ATLWSH-ATL", _pass())
        raise AssertionError("kill should block")
    except PaperBlocked as exc:
        assert "kill" in str(exc).lower()
    ledger.reset_kill()
    # still 30% down until peak is rebuilt — reset clears the flag only
    assert not ledger.killed()
