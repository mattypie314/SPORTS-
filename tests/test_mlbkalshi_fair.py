from pathlib import Path

from mlbkalshi.fair import BookOutcome, FairIndex, fetch_odds_api, load_book_file, parse_book_row


def _row(**kwargs) -> BookOutcome:
    base = dict(
        book="pinnacle",
        market="h2h",
        commence="2026-09-02T23:10:00Z",
        away="ATL",
        home="WSH",
        outcome="ATL",
        american=-150,
    )
    base.update(kwargs)
    return parse_book_row(base)


def test_csv_and_json_book_drop(tmp_path: Path):
    csv_path = tmp_path / "books.csv"
    csv_path.write_text(
        "book,commence,away,home,market,outcome,american\n"
        "pinnacle,2026-09-02T23:10:00Z,ATL,WSH,h2h,ATL,-150\n"
        "pinnacle,2026-09-02T23:10:00Z,ATL,WSH,h2h,WSH,130\n"
    )
    rows = load_book_file(csv_path)
    assert len(rows) == 2
    assert rows[0].away == "ATL"
    json_path = tmp_path / "books.json"
    json_path.write_text(
        '[{"book":"circa","commence":"2026-09-02T23:10:00Z","away":"Atlanta Braves",'
        '"home":"Washington Nationals","market":"h2h","outcome":"WSH","american":130},'
        '{"book":"circa","commence":"2026-09-02T23:10:00Z","away":"Atlanta",'
        '"home":"Washington","market":"h2h","outcome":"ATL","american":-150}]'
    )
    assert len(load_book_file(json_path)) == 2


def test_consensus_median_and_disagreement():
    rows = [
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02T23:10:00Z",
                away="ATL",
                home="WSH",
                market="h2h",
                outcome="ATL",
                american=-150,
            )
        ),
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02T23:10:00Z",
                away="ATL",
                home="WSH",
                market="h2h",
                outcome="WSH",
                american=130,
            )
        ),
        parse_book_row(
            dict(
                book="circa",
                commence="2026-09-02T23:10:00Z",
                away="ATL",
                home="WSH",
                market="h2h",
                outcome="ATL",
                american=-170,
            )
        ),
        parse_book_row(
            dict(
                book="circa",
                commence="2026-09-02T23:10:00Z",
                away="ATL",
                home="WSH",
                market="h2h",
                outcome="WSH",
                american=150,
            )
        ),
    ]
    index = FairIndex.build(rows)
    hit = index.lookup(date_key="2026-09-02", away="ATL", home="WSH", market="h2h", outcome="ATL")
    assert hit is not None
    assert hit.deep
    assert hit.source in {"pinnacle", "circa", "sharp_median"}
    assert hit.disagree_pts >= 0
    other = index.lookup(date_key="2026-09-02", away="WSH", home="ATL", market="h2h", outcome="WSH")
    assert other is not None
    assert abs(hit.fair + other.fair - 1.0) < 1e-9


def test_spread_and_total_lookup():
    rows = [
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02",
                away="BAL",
                home="COL",
                market="spreads",
                outcome="BAL",
                point=-1.5,
                american=-110,
            )
        ),
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02",
                away="BAL",
                home="COL",
                market="spreads",
                outcome="COL",
                point=1.5,
                american=-110,
            )
        ),
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02",
                away="BAL",
                home="COL",
                market="totals",
                outcome="OVER",
                point=8.5,
                american=-105,
            )
        ),
        parse_book_row(
            dict(
                book="pinnacle",
                commence="2026-09-02",
                away="BAL",
                home="COL",
                market="totals",
                outcome="UNDER",
                point=8.5,
                american=-115,
            )
        ),
    ]
    index = FairIndex.build(rows)
    spread = index.lookup(
        date_key="2026-09-02", away="BAL", home="COL", market="spreads", outcome="BAL", point=-1.5
    )
    total = index.lookup(
        date_key="2026-09-02", away="BAL", home="COL", market="totals", outcome="OVER", point=8.5
    )
    assert spread is not None and spread.fair == 0.5
    assert total is not None and 0.4 < total.fair < 0.6


def test_odds_api_adapter(monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return [
                {
                    "commence_time": "2026-09-02T23:10:00Z",
                    "home_team": "Washington Nationals",
                    "away_team": "Atlanta Braves",
                    "bookmakers": [
                        {
                            "key": "pinnacle",
                            "markets": [
                                {
                                    "key": "h2h",
                                    "outcomes": [
                                        {"name": "Atlanta Braves", "price": -150},
                                        {"name": "Washington Nationals", "price": 130},
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ]

    class FakeClient:
        def get(self, url, params=None):
            assert "baseball_mlb" in url
            assert params["markets"] == "h2h,spreads,totals"
            return FakeResp()

        def close(self):
            return None

    rows = fetch_odds_api("dummy", client=FakeClient())
    assert len(rows) == 2
    assert {row.outcome for row in rows} == {"ATL", "WSH"}
