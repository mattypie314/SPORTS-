from sportsbot.cli import build_parser


def test_parser_has_expected_commands():
    parser = build_parser()
    args = parser.parse_args(["scan", "--league", "nfl", "--json"])
    assert args.command == "scan"
    assert args.league == ["nfl"]
    assert args.json is True


def test_paper_status_flag():
    parser = build_parser()
    args = parser.parse_args(["paper", "--status"])
    assert args.status is True
