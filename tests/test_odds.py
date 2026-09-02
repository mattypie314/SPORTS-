from sportsbot.odds import american_to_prob, devig, names_match, normalize_name


def test_normalize_and_match():
    assert names_match("Seattle", "Seattle Seahawks")
    assert names_match("New England", "New England Patriots")
    assert not names_match("Seattle", "Dallas")
    assert "seahawks" in normalize_name("Seattle Seahawks")


def test_devig_american():
    raw = [american_to_prob(-150), american_to_prob(130)]
    fair = devig(raw)
    assert abs(sum(fair) - 1) < 1e-9
    assert fair[0] > fair[1]
