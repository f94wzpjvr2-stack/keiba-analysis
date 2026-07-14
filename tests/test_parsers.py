from keiba_ev.odds_parser import parse_quinella_text, parse_trio_text, parse_wide_text


def test_wide_parser_uses_low_odds():
    parsed = parse_wide_text("1-2\t18.6-20.0\n2-3 7.2-8.1")
    assert parsed.loc[parsed["selection"] == "1-2", "odds"].item() == 18.6


def test_quinella_parser():
    parsed = parse_quinella_text("1-2\t68.1\n2-3 15.4")
    assert parsed.loc[parsed["selection"] == "1-2", "odds"].item() == 68.1


def test_trio_parser_with_popularity_column():
    parsed = parse_trio_text("1 1-2-3 15.0\n2 2-3-4 18.5")
    assert parsed.loc[parsed["selection"] == "1-2-3", "odds"].item() == 15.0
