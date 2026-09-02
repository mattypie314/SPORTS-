from mlbkalshi.fair import FairIndex, parse_book_row
from mlbkalshi.scanner import scan_events


def _game_event():
    return {
        "event_ticker": "KXMLBGAME-26SEP02ATLWSH",
        "title": "Atlanta vs Washington",
        "markets": [
            {
                "ticker": "KXMLBGAME-26SEP02ATLWSH-ATL",
                "status": "active",
                "yes_sub_title": "Atlanta",
                "yes_bid_dollars": "0.54",
                "yes_ask_dollars": "0.55",
            },
            {
                "ticker": "KXMLBGAME-26SEP02ATLWSH-WSH",
                "status": "active",
                "yes_sub_title": "Washington",
                "yes_bid_dollars": "0.44",
                "yes_ask_dollars": "0.45",
            },
        ],
    }


def _spread_event():
    return {
        "event_ticker": "KXMLBSPREAD-26SEP02BALCOL",
        "title": "Baltimore vs Colorado: Spread",
        "markets": [
            {
                "ticker": "KXMLBSPREAD-26SEP02BALCOL-BAL2",
                "status": "active",
                "yes_sub_title": "Baltimore wins by over 1.5 runs",
                "title": "Baltimore wins by over 1.5 runs?",
                "floor_strike": 1.5,
                "yes_bid_dollars": "0.48",
                "yes_ask_dollars": "0.49",
            }
        ],
    }


def test_scan_moneyline_with_books_can_pass():
    rows = [
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02",
                away="ATL",
                home="WSH",
                market="h2h",
                outcome="ATL",
                american=-300,
            )
        ),
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02",
                away="ATL",
                home="WSH",
                market="h2h",
                outcome="WSH",
                american=220,
            )
        ),
    ]
    found = scan_events([_game_event()], "KXMLBGAME", 100, fairs=FairIndex.build(rows), models=None)
    atl = next(row for row in found if row.team == "ATL")
    assert atl.result.passed
    assert atl.result.source_of_fair == "pinnacle"
    assert not atl.result.extras.get("low_confidence")


def test_scan_degraded_model_fails_below_ten():
    class Fake:
        win_pct = 0.55
        pythag = 0.55
        era = None
        source = "standings"

    models = {"ATL": Fake(), "WSH": Fake()}
    # monkey: model_win_prob reads .win_pct/.pythag — Fake works if we pass objects
    from mlbkalshi.model_fair import ModelFair

    models = {
        "ATL": ModelFair("ATL", 0.58, 0.58),
        "WSH": ModelFair("WSH", 0.42, 0.42),
    }
    found = scan_events([_game_event()], "KXMLBGAME", 100, fairs=None, models=models)
    assert found
    assert all(not row.result.passed for row in found)
    assert all(row.result.source_of_fair == "model_fair" for row in found)


def test_scan_spread_matches_book_line():
    rows = [
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02",
                away="BAL",
                home="COL",
                market="spreads",
                outcome="BAL",
                point=-1.5,
                american=-200,
            )
        ),
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02",
                away="BAL",
                home="COL",
                market="spreads",
                outcome="COL",
                point=1.5,
                american=170,
            )
        ),
    ]
    found = scan_events([_spread_event()], "KXMLBSPREAD", 100, fairs=FairIndex.build(rows))
    assert found
    assert found[0].series == "KXMLBSPREAD"
    assert "BAL" in found[0].team


def test_scan_spread_without_books_is_empty():
    assert scan_events([_spread_event()], "KXMLBSPREAD", 100, fairs=None) == []


def test_skip_lopsided_nine_inning_moneyline():
    from mlbkalshi.model_fair import ModelFair

    live = _game_event()
    live["markets"][0]["yes_bid_dollars"] = "0.97"
    live["markets"][0]["yes_ask_dollars"] = "0.98"
    live["markets"][1]["yes_bid_dollars"] = "0.02"
    live["markets"][1]["yes_ask_dollars"] = "0.03"
    models = {
        "ATL": ModelFair("ATL", 0.55, 0.55),
        "WSH": ModelFair("WSH", 0.45, 0.45),
    }
    assert scan_events([live], "KXMLBGAME", 100, fairs=None, models=models) == []
