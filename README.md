# Kalshi Sports Bot

Paper-first trading bot for [Kalshi](https://kalshi.com) sports markets. It pulls live NFL, NCAAF, MLB, NBA, NHL, and MLS game-winner contracts, prints a board, flags edges, and can paper-trade them. Real-money orders stay off unless you explicitly enable them.

## What it does

- **Board** — live moneyline prices, implied American odds, and volume
- **Signals**
  - complementary arb (YES asks on a mutually exclusive game sum to less than $1)
  - complementary sell arb (YES bids sum to more than $1)
  - wide books
  - last-price moves
  - optional sportsbook value vs [The Odds API](https://the-odds-api.com)
- **Paper book** — SQLite ledger, bankroll, daily cap, max positions
- **Dashboard** — local sports terminal at `http://127.0.0.1:8000`
- **Live** — Kalshi RSA-signed orders, demo by default, requires env flags plus `--confirm-live`

Market data always comes from Kalshi production (`https://external-api.kalshi.com/trade-api/v2`). No API key is needed to scan.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Use

```bash
# Live board + signals (no credentials)
sportsbot scan --league nfl --league mlb

# JSON for scripts
sportsbot scan --json

# Paper-trade any actionable arb / sportsbook value
sportsbot paper

# Paper book
sportsbot paper --status

# Local dashboard
sportsbot dashboard --port 8000
```

Copy `.env.example` to `.env` to set bankroll, risk caps, and optional keys.

### Risk defaults

| Limit | Default |
| --- | --- |
| Starting paper cash | $1,000 |
| Max notional per signal | $25 |
| Daily spend cap | $200 |
| Max open events | 8 |
| Minimum arb / value edge | 2¢ |

Create `data/KILL` to halt new paper (and live) entries.

### Optional sportsbook comparison

Set `ODDS_API_KEY` and rescan. The bot vig-frees the first US bookmaker h2h quote and flags Kalshi asks cheaper than that fair probability.

### Live trading (off by default)

1. Create an API key in Kalshi account settings and save the RSA private key.
2. Set `KALSHI_API_KEY_ID`, `KALSHI_PRIVATE_KEY_PATH`, and `KALSHI_ENABLE_LIVE=true`.
3. `KALSHI_ENV=demo` (default) or `prod`.
4. Dry-run, then confirm:

```bash
sportsbot live --league nfl --dry-run
sportsbot live --league nfl --confirm-live
```

Live mode only sends IOC bids for `arb_buy` and `sportsbook_value`. Prediction-market trading can lose money. This is not financial advice.

## Tests

```bash
pytest
```

## API used

- `GET /series?category=Sports`
- `GET /events?series_ticker=KXNFLGAME&status=open&with_nested_markets=true`
- `POST /portfolio/events/orders` (live only)
