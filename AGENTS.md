# mlbkalshi

Production MLB scanner and paper trader for Kalshi event contracts.

Read this file, `.cursor/rules/mlb-kalshi-bot.mdc`, `docs/ARCHITECTURE.md`, and `docs/settlement.md` before changing strategy, sizing, or settlement logic.

## Mission

Find +EV Kalshi MLB trades by comparing Kalshi Yes/No prices to **no-vig sharp sportsbook consensus**. Filter first. Size second. Paper-trade by default. Do not invent alpha on top of the books unless a model is explicitly supplied.

`src/v0_standings_scanner/` is a working public-API scanner. Keep it runnable. It is **not** the live trigger.

## Non-negotiable rules

1. Only recommend a trade when **net EV after estimated fees ≥ 6%**. Use a **4%** floor only if books agree tightly (disagreement ≤ 2 pts) **and** the Kalshi spread is 1–2¢.
2. Primary fair value = no-vig book consensus (Pinnacle / Circa / sharp median). Standings / pythag / ERA models are a **fallback label**, never the live trigger.
3. Prefer maker / limit orders. Taker fee ≈ `0.07 * p * (1-p)` per contract. Maker fee ≈ `0.0175 * p * (1-p)`.
4. Fractional Kelly **0.25–0.35×** (default 0.30). Cap risk at **5–8%** of bankroll (default 6%). Default bankroll **$100** if unset, **$35** if `SMALL_BANKROLL=1`.
5. If nothing passes: print `No actionable edge` and list closest misses. Do not force a bet.
6. Do not place live Kalshi orders unless `LIVE_TRADING=1` and keys exist. Default is paper.
7. Settlement follows **Kalshi contract language**, not sportsbook void rules. Read `docs/settlement.md` before any non-standard market.
8. No revenge trading. No averaging into a live game unless the contract is F5 / RFI and the math still clears after the new state.
9. Skip **80¢+ favorites** and **15¢ longshots** unless net EV ≥ 10% and the book is deep.
10. This is not financial advice. Contracts can expire at $0.

## Boxed recommendation format

Print **only PASS rows** in this box. FAIL / skip rows belong under `No actionable edge` as closest misses.

```
┌──────────────────────────────────────────────────────────────┐
│ PASS   {TEAM} {SIDE} @ {price:.2f}                           │
│ Fair   {fair:.3f}  ({source})  Δbooks {disagree_pts:.1f}     │
│ NetEV  {net_ev:+.1%}  fee {fee:.3f}  {taker|maker}           │
│ Size   {contracts:.2f}c   risk ${risk:.2f}   Kelly {k:.2f}×  │
│ Why    {reason}                                              │
└──────────────────────────────────────────────────────────────┘
```

If the slate is empty of PASSes:

```
No actionable edge

Closest misses:
  FAIL  LAD YES @ 0.72  netEV +3.1%  below 6% gate
```

## Commands

```bash
python -m v0_standings_scanner
python scripts/mlb_edge.py --book-odds -150 +130 --kalshi 0.55 --side yes --bankroll 100
python -m mlbkalshi markets --series KXMLBGAME
python -m mlbkalshi edge --book-odds -150 +130 --kalshi 0.55 --side yes --bankroll 100
python -m mlbkalshi scan --bankroll 100
python -m pytest -q
```

`scan` must run with no `ODDS_API_KEY` (degraded: Kalshi mid vs standings model, every row tagged `low_confidence`, default FAIL unless EV ≥ 10%).

## Series in scope

| Series | Market |
| --- | --- |
| `KXMLBGAME` | Game winner (moneyline) |
| `KXMLBSPREAD` | Game spread |
| `KXMLBTOTAL` | Game total runs |
| `KXMLBRFI` | Run in first inning |
| `KXMLBF5SPREAD` | First five innings spread |
