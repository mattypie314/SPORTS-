from mlbkalshi.names import codes_from_event_title, parse_ticker, team_code


def test_split_markets():
    assert team_code("LAD") == "LAD"
    assert team_code("LAA") == "LAA"
    assert team_code("NYY") == "NYY"
    assert team_code("NYM") == "NYM"
    assert team_code("CHC") == "CHC"
    assert team_code("CWS") == "CWS"
    assert team_code("ATH") == "ATH"
    assert team_code("A's") == "ATH"
    assert team_code("New York Y") == "NYY"
    assert team_code("New York M") == "NYM"
    assert team_code("Chicago C") == "CHC"
    assert team_code("Chicago WS") == "CWS"
    assert team_code("Los Angeles D") == "LAD"
    assert team_code("Los Angeles A") == "LAA"
    assert team_code("Texas") == "TEX"
    assert team_code("Athletics") == "ATH"


def test_parse_game_ticker():
    parsed = parse_ticker("KXMLBGAME-26SEP02ATLWSH-ATL")
    assert parsed.series == "KXMLBGAME"
    assert parsed.date == "26SEP02"
    assert parsed.outcome == "ATL"


def test_parse_timed_ticker():
    parsed = parse_ticker("KXMLBGAME-26SEP021305ATLWSH-WSH")
    assert parsed.series == "KXMLBGAME"
    assert parsed.date == "26SEP02"
    assert parsed.outcome == "WSH"


def test_event_title_vs():
    assert codes_from_event_title("Atlanta vs Washington") == ("ATL", "WSH")
    assert codes_from_event_title("A's vs Texas") == ("ATH", "TEX")
    assert codes_from_event_title("New York Y vs Los Angeles A") == ("NYY", "LAA")
    assert codes_from_event_title("Baltimore vs Colorado: Spread") == ("BAL", "COL")
    assert codes_from_event_title("New York M vs Tampa Bay: First Inning Run") == ("NYM", "TB")


def test_kalshi_date_and_ticker_teams():
    from datetime import date

    from mlbkalshi.names import event_date_from_ticker, team_code_from_text, teams_from_ticker

    assert event_date_from_ticker("KXMLBGAME-26SEP021305ATLWSH-ATL") == date(2026, 9, 2)
    assert teams_from_ticker("KXMLBGAME-26SEP021305ATLWSH-ATL") == ("ATL", "WSH")
    assert teams_from_ticker("KXMLBGAME-26SEP022010CWSHOU-HOU") == ("CWS", "HOU")
    assert teams_from_ticker("KXMLBGAME-26SEP022138NYYLAA-NYY") == ("NYY", "LAA")
    assert team_code_from_text("Colorado wins by over 3.5 runs") == "COL"
    assert team_code_from_text("Tampa Bay -2.5 first 5 innings") == "TB"
