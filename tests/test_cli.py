from sportsbot.cli import build_parser


def test_parser_has_expected_commands():
    parser = build_parser()
    args = parser.parse_args(["scan", "--json"])
    assert args.command == "scan"
    assert args.json is True


def test_paper_status_flag():
    parser = build_parser()
    args = parser.parse_args(["paper", "--status"])
    assert args.status is True


def test_scan_rejects_league_flag():
    parser = build_parser()
    try:
        parser.parse_args(["scan", "--league", "nfl"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected --league to be rejected")
