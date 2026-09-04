# Kalshi MLB settlement

Kalshi event contracts settle from **Kalshi rulebooks and listed sources**, not from a sportsbook ticket. Do not assume a sportsbook void, push, or official scoring change applies to a Kalshi ticker until the contract language says so.

## Game winner (`KXMLBGAME`)

- Yes on a team typically pays if that team is the winner of the listed regular-season or playoff game.
- Extra innings count unless the contract says otherwise.
- Postponements / postponement-to-another-date follow the series terms (often the game must be played by a listed deadline).

## Spread (`KXMLBSPREAD`) and total (`KXMLBTOTAL`)

- Spreads and totals use the official final score after extras unless the market is explicitly F5 / first-N-innings.
- A sportsbook “no action” on a pitcher change does **not** automatically void a Kalshi game spread or total.

## First five (`KXMLBF5SPREAD`, `KXMLBF5`)

- Settles on the score after 5 innings (or the Kalshi-defined first-five window).
- If the game is called before that window is official, read the event rules — do not infer a sportsbook F5 void.

## Run first inning (`KXMLBRFI`)

- Yes if at least one run scores in the first inning of the listed game.
- Called / delayed games: follow Kalshi, not NRFI sportsbook house rules.

## Playoff games that may not be played (Game 5 / 6 / 7)

If the series ends before the game is played, Kalshi typically **does not void** the way a sportsbook future might. Many Kalshi playoff game contracts **resolve to the last fair / last traded price** (or another stated mark) rather than $0 / $1.

**Never treat an unplayed playoff Game 5/6/7 as a sportsbook void.** Do not paper a “void = get stake back” outcome unless the specific ticker’s terms say that.

## Live trading

Do not average into a live 9-inning moneyline / full-game spread / full-game total unless you have rebuilt fair value from the new state **and** the contract is F5 or RFI **and** net EV still clears the gate.
