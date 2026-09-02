from v0_standings_scanner.scanner import ALIASES, resolve_code, TeamRow


def test_alias_oakland_athletics():
    standings = {"ATH": TeamRow(code="ATH", name="Athletics", win_pct=0.5)}
    assert resolve_code("A's", standings) == "ATH"
    assert resolve_code("Athletics", standings) == "ATH"


def test_split_city_codes():
    standings = {
        "NYY": TeamRow(code="NYY", name="New York Yankees", win_pct=0.6),
        "NYM": TeamRow(code="NYM", name="New York Mets", win_pct=0.5),
        "LAD": TeamRow(code="LAD", name="Los Angeles Dodgers", win_pct=0.6),
        "LAA": TeamRow(code="LAA", name="Los Angeles Angels", win_pct=0.4),
        "CHC": TeamRow(code="CHC", name="Chicago Cubs", win_pct=0.5),
        "CWS": TeamRow(code="CWS", name="Chicago White Sox", win_pct=0.4),
    }
    assert resolve_code("New York Y", standings) == "NYY"
    assert resolve_code("New York M", standings) == "NYM"
    assert resolve_code("Los Angeles D", standings) == "LAD"
    assert resolve_code("Los Angeles A", standings) == "LAA"
    assert resolve_code("Chicago C", standings) == "CHC"
    assert resolve_code("Chicago WS", standings) == "CWS"
    assert ALIASES["a's"] == "ATH"
