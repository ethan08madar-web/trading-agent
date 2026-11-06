# Research upgrade — design

**Date:** 2026-11-06 · **Status:** proposed, waiting for Ethan's go
**Goal (Ethan's words):** "do as much research as you can before getting a stock… do what you
think will perform best… we'll test it out, if adjustments need to be made, we'll make adjustments."

## 1. The problem

Today the morning plan finds candidates with screeners, drops broken data and earnings risks,
and sets entry/stop/target from simple price levels (`robot/research.py`). Nobody knows whether
these rules make money: the 1-week paper test is far too short to tell (a few trades at most).

Adding more research layers blindly could make picks *worse* and we would never notice. So
the upgrade is built around a **scoreboard** that measures every rule change on past years
before it is trusted.

## 2. Decisions (Ethan delegated the choices on 2026-11-06)

| Decision | Choice | Why | Rejected |
|---|---|---|---|
| Build order | 1 scoreboard → 2 per-stock history + odds → 3 extra layers | Each later piece needs the scoreboard to prove it helps | Layers first (nothing proves they help) |
| What the scoreboard replays | A **mechanical twin**: rules a computer follows alone | Replaying Claude's judgment for every past day would use up the Pro allowance | Claude on a sample of days (tiny sample, costly) |
| Pass mark | Beat buy-and-hold SPY on the **held-out years**, measured as yearly return ÷ worst drop (higher wins), while also making at least SPY's yearly return minus 2 points; ≥100 trades across the whole 2019→today run | Holding SPY is free and effortless; the bot has to earn its complexity | "Makes money at all" (a weak bar) |
| Data | Alpaca daily bars, full market feed (`feed=sip`), free | Already used, no new key, 0 FMP calls | FMP history (uses the 250/day free calls) |
| Stocks tested | Past S&P 500 members **as of each date** (`fja05680/sp500` CSV) | Testing only today's members hides the companies that failed (survivorship bias) | Today's list only |
| Rule code | Backtest reuses `robot/safety.py`; the exit decision moves from `robot/main.py` into one shared function | One copy of the rules, so the twin can't drift from the real Robot | A separate rule copy, or `manifoldbt-backtester` (one symbol, one entry rule; can't model 4 positions, half-sells or the safety brake; license restrictions) |
| "Thousands of predictions" | A per-trade odds simulator (bootstrap of the stock's own daily moves), labelled honestly as odds, not a forecast | Random futures can't know direction, but they do measure "stop before target" odds and sensible stop distance | Presenting simulations as predictions |

## 3. Piece 1 — the scoreboard (`backtest/`)

**What it does:** walks day by day through 2019-01 → today with a pretend $1,000 account and
runs each **rulebook** exactly as the Robot would, then writes a plain-language report.

**Years:** rules may be tuned on **2019–2023** only. **2024 → today is held out**: it is run once
per finished rulebook and never used for tuning. This is the guard against "fitting the past."

**A day in the replay:**
1. Market light from that day's data only: share of stocks above their 50-day average, plus
   SPY vs its 50- and 200-day averages → green / yellow / red, `light_falling`.
2. Candidates from the rulebook's pattern finder, as of that day (no future bars).
3. Same checks as `robot/research.py`: drop bad data; default entry/stop/target from `levels()`.
4. Entries next day: bought if that day's low reaches `entry_max` and stays above the stop;
   fill at the lower of the open and `entry_max`. Size from `safety.position_size`; slot cap from
   `safety.max_positions_for`; safety brake from `safety.breaker_reason`.
5. Exits with the shared exit function (stop → earnings → below 20-day average → half at target,
   stop to entry). A gap below the stop fills at the open, not the stop.
6. Costs: 0.10% slippage per side (the free broker has no commission).

**Earnings:** past earnings dates aren't free in bulk. The twin approximates "skip earnings" by
skipping days with an earnings-sized gap (±7% open vs prior close) and notes the gap. Reported
as a known weakness, not hidden.

**Rulebooks (contestants), all mechanical:**
- **A. Today's twin** — the current bot: VCP + momentum-burst patterns, current levels.
- **B. Momentum leaders** — the strongest stocks over 6 and 12 months (relative strength vs SPY),
  in an uptrend (above 50- and 200-day), bought on a pullback toward the 20-day average.
- **C. Breakout leaders** — same leaders, bought when they clear their 20-day high on rising volume.
- **D. Trend only** — SPY when above its 200-day average, cash otherwise.
- **Benchmark** — buy and hold SPY.

B and C are included because "buy what has been rising strongly" (momentum) is one of the
best-documented patterns in stock-market research; A has no track record yet. The scoreboard,
not the literature, decides.

**Report (`backtest/results/<date>-report.md`, committed; price cache gitignored):**
per rulebook — end balance, vs SPY, worst drop, win rate, average win / loss, number of
trades, best and worst year, tune years vs held-out years side by side. Graded with the
library's `backtest-expert` evaluator (`evaluate_backtest.py`) for red flags (too few trades,
results that only work with one exact setting). One line at the top in plain words: which
rulebook passed and by how much, or "none passed."

**Runs on:** Ethan's PC or a manual GitHub Actions workflow. Uses no Claude allowance and no FMP calls.

## 4. Piece 2 — per-stock history and odds in the morning plan

Extends `robot/research.py` (0 extra FMP calls; Alpaca bars only). Every KEEP line gains:

- **History:** past times *this* stock showed the winning rulebook's setup (the VCP historical
  scanner already in the library does this for VCP) → how many, how many worked, average result.
- **Odds:** 2,000 simulated futures from the stock's own last-year daily moves → chance the stop
  is hit before the target, and the typical days to either. Labelled "odds, not a forecast."

Claude ranks picks with these. Whether "skip picks with odds below X" improves results is
itself tested on the scoreboard before it becomes a rule.

## 5. Piece 3 — extra research layers, one at a time

Each layer is a switch in the scoreboard and is kept **only if it improves the tune-years
result and doesn't hurt the held-out years**:

1. Relative strength vs SPY (part of B/C already).
2. Sector strength — only buy from the strongest sectors (sector funds' trends).
3. Volume confirmation — breakouts on above-average volume.
4. Earnings drift — strong stocks after a positive earnings surprise (needs past earnings data;
   only if a free source holds up, otherwise listed for the FMP-paid decision).

**News** can't be replayed cheaply, so it is never a buy signal. In the live morning plan only,
it is a **veto**: Claude reads the latest headlines for each pick (`market-news-analyst`) and drops
a stock with fresh bad news (lawsuit, share sale, guidance cut, CEO exit), saying why.

## 6. What changes for the live bot

Nothing until a rulebook passes. Then the winning rulebook's settings go into the morning plan
routine and `robot/research.py`, with Ethan's OK, and the paper test continues. The Robot's
safety limits (1% risk, 4 positions, 30% cap, brake) never loosen.

## 7. Testing

- Unit tests (`tests/`) for: the shared exit function (same answers as before the move), the
  market-light calculation, next-day fill rules (incl. a gap below the stop), the odds
  simulator (a stock that only rises never hits its stop), and "no future bars" (a candidate
  finder given day N data can't see day N+1 — a test that breaks if it does).
- The existing 68 tests must still pass after the exit function moves.
- A tiny hand-checked replay (2 stocks, 30 days) whose trades are worked out by hand.

## 8. Known limits (say these out loud in every report)

- Daily bars, not 15-minute checks: fills are approximate.
- Earnings approximated by price gaps until real past earnings dates are available.
- Delisted companies may lack Alpaca history; any missing ones are counted and listed.
- Past results don't guarantee future ones. Passing means "worth paper-testing longer", not "safe".
