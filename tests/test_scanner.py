from sportsbot.scanner import event_from_api


def test_event_from_api_skips_inactive():
    raw = {
        "event_ticker": "KXNFLGAME-1",
        "series_ticker": "KXNFLGAME",
        "title": "NE vs SEA",
        "sub_title": "NE vs SEA",
        "mutually_exclusive": True,
        "markets": [
            {
                "ticker": "A",
                "status": "closed",
                "yes_sub_title": "A",
                "title": "A wins",
                "yes_bid_dollars": "0.40",
                "yes_ask_dollars": "0.41",
                "volume_fp": "10",
                "open_interest_fp": "1",
            },
            {
                "ticker": "B",
                "status": "active",
                "yes_sub_title": "B",
                "title": "B wins",
                "yes_bid_dollars": "0.58",
                "yes_ask_dollars": "0.59",
                "volume_fp": "10",
                "open_interest_fp": "1",
            },
        ],
    }
    event = event_from_api(raw, "nfl")
    assert event is not None
    assert len(event.markets) == 1
    assert event.markets[0].team == "B"


def test_event_from_api_empty_when_no_active():
    raw = {
        "event_ticker": "X",
        "series_ticker": "KXNFLGAME",
        "title": "Gone",
        "markets": [{"ticker": "A", "status": "settled", "title": "A"}],
    }
    assert event_from_api(raw, "nfl") is None
