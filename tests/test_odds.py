from sportsbot.odds import american_to_prob, devig, names_match, normalize_name


def test_normalize_and_match():
    assert names_match("Atlanta", "Atlanta Braves")
    assert names_match("New York Y", "New York Yankees")
    assert not names_match("Atlanta", "Boston")
    assert "braves" in normalize_name("Atlanta Braves")


def test_devig_american():
    raw = [american_to_prob(-150), american_to_prob(130)]
    fair = devig(raw)
    assert abs(sum(fair) - 1) < 1e-9
    assert fair[0] > fair[1]
