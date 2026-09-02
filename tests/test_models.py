from sportsbot.kalshi.models import EventMarkets, GameMarket, format_american, implied_to_american, parse_dollars


def test_parse_dollars():
    assert parse_dollars("0.6300") == 0.63
    assert parse_dollars(None) is None
    assert parse_dollars("") is None


def test_american_odds():
    assert implied_to_american(0.5) == -100
    assert implied_to_american(0.75) == -300
    assert implied_to_american(0.25) == 300
    assert format_american(150) == "+150"
    assert format_american(-110) == "-110"


def sample_market(**overrides) -> GameMarket:
    payload = {
        "ticker": "KXMLBGAME-26SEP02ATLWSH-ATL",
        "event_ticker": "KXMLBGAME-26SEP02ATLWSH",
        "yes_sub_title": "Atlanta",
        "title": "Atlanta wins",
        "status": "active",
        "yes_bid_dollars": "0.6200",
        "yes_ask_dollars": "0.6300",
        "no_bid_dollars": "0.3700",
        "no_ask_dollars": "0.3800",
        "last_price_dollars": "0.6300",
        "previous_price_dollars": "0.6000",
        "volume_fp": "1000.00",
        "open_interest_fp": "500.00",
        "close_time": "2026-09-12T00:20:00Z",
        "occurrence_datetime": "2026-09-09T00:20:00Z",
    }
    payload.update(overrides)
    event = {
        "event_ticker": "KXMLBGAME-26SEP02ATLWSH",
        "series_ticker": "KXMLBGAME",
        "title": "Atlanta vs Washington",
        "sub_title": "ATL vs WSH (Sep 2)",
        "mutually_exclusive": True,
    }
    return GameMarket.from_api(payload, event, "mlb", "MLB")


def test_market_mid_and_spread():
    market = sample_market()
    assert market.mid == 0.625
    assert market.spread == 0.01
    assert market.team == "Atlanta"
    assert market.league == "mlb"


def test_event_kickoff_uses_occurrence():
    market = sample_market()
    event = EventMarkets(
        event_ticker=market.event_ticker,
        series_ticker="KXMLBGAME",
        title="Atlanta vs Washington",
        subtitle="ATL vs WSH",
        league="mlb",
        league_label="MLB",
        mutually_exclusive=True,
        occurrence=None,
        markets=[market],
    )
    assert event.kickoff is not None
    assert event.to_dict()["markets"][0]["ticker"] == market.ticker
