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
