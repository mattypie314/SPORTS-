# mlbkalshi architecture

Layered scanner. Each layer can run without the one above it.

```
Kalshi public markets ──┐
                        ├─► match (date + team codes) ─► EV / fees / Kelly ─► PASS box
Book lines / CSV ───────┤                                              │
MLB Stats model_fair ───┘                                              ▼
                                                              paper ledger
                                                              (live only if LIVE_TRADING=1)
```

## Packages

| Path | Role |
| --- | --- |
| `src/v0_standings_scanner/` | Phase 0 public-API board. Standings win% vs Kalshi mid. **Not** the live trigger. |
| `src/mlbkalshi/odds.py` | American → implied → two-way / multi-way no-vig |
| `src/mlbkalshi/fees.py` | Taker/maker, gross EV, net EV, Kelly, size |
| `src/mlbkalshi/kalshi_public.py` | Paginated public Trade API + 429 backoff |
| `src/mlbkalshi/names.py` | Kalshi labels ↔ MLB team codes |
| `src/mlbkalshi/fair.py` | Book adapters + consensus + disagreement |
| `src/mlbkalshi/scanner.py` | Slate scan across MLB series |
| `src/mlbkalshi/paper.py` | CSV ledger, daily idea cap, drawdown kill |
| `src/mlbkalshi/live.py` | Signed portfolio / Create Order behind env flag |
| `scripts/mlb_edge.py` | Thin CLI around `fees` + `odds` (same as `mlbkalshi edge`) |

## Fair-value precedence

1. No-vig median of available sharp-ish books (Pinnacle, Circa, then other US books).
2. If books disagree by **> 4 points**, raise the EV gate to **8%** or skip.
3. If no book lines: standings / pythag / pitcher ERA as `model_fair`, tag `low_confidence`. Those rows FAIL unless net EV ≥ 10%.

## Net EV

For a Yes bid/ask at price `p` and fair `f`:

```
gross_ev = f - p
fee      = rate * p * (1 - p)     # 0.07 taker, 0.0175 maker
net_ev   = gross_ev - fee         # probability points on a $1 contract
```

A 6% gate means `net_ev >= 0.06`.

## Risk

```
kelly_full = (f - p) / (1 - p)     # Yes, price p, fair f
stake      = bankroll * kelly_full * kelly_fraction
stake      = min(stake, bankroll * risk_cap)
contracts  = stake / p
```

Default `kelly_fraction=0.30`, `risk_cap=0.06`.

## Live vs paper

| Mode | When |
| --- | --- |
| Paper | Default. CSV ledger only. |
| Live | `LIVE_TRADING=1` **and** `KALSHI_API_KEY_ID` + private key. RSA-PSS. |

v0 never places orders.
