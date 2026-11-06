# Session — 2026-11-06 — trading-agent

**Date:** 2026-11-06
**Project:** trading-agent
**Branch:** main (work done on short branches, each merged `--no-ff`)

## Goals

Finish setup from session 2: shrink the paper account to ~$1,000, FMP key, cloud environment, create
the 4 Claude routines, run Plan once. Mid-session Ethan added two more: make Mission Control look like a
broker app ("like Robinhood"), and make Telegram messages easier to read.

## Completed

- **Paper account:** Alpaca has no reset button, only "New Paper Account" + "Delete". Ethan made a new
  $1,000 account (PA3ILFRGT), regenerated its keys and replaced both GitHub secrets. The old $100k account
  (PA3FRQ58C) is kept until the new keys are proven.
- **Robot memory reset:** `notebook/state.json` → `{}`. It held `week_start_equity: 100000`, so the weekly
  brake would have read −99% against $1,000 and paused all buying.
- **FMP:** Ethan made a free account.
- **Cloud environment `trading-agent`** (`env_01F52Mi5WxZm2JmryHCgFBaD`), created by Claude in Chrome with
  Ethan's OK. It has the repo, Limited network with 10 domains (3 Alpaca, FMP, Telegram, 2 Yahoo,
  `tradermonty.github.io`, 2 Artifact frame domains), and a 3-line setup script (pip install
  requests/pyyaml/numpy/pandas for `python3` and `python`). Ethan typed the 7 keys into Environment
  variables himself.
- **4 routines** were created with `RemoteTrigger` (IDs and cron are in CLAUDE.md), then connectors cleared.
- **Manual Plan run** (11:10 UTC) succeeded in 92 s. It committed the plan (191af77), sent 📋 Telegram
  (HTTP 200), got Alpaca prices + FMP earnings, and republished Mission Control at the same URL (v3).
  Red light → no picks.
- **Mission Control redesign** (`robot/dashboard.py`): big account value + week change (▲/▼ + sign, not
  color alone); an inline-SVG equity line you can scrub (pointer + arrow keys; Escape resets) with a dashed
  week-start baseline; three market-light lamps; plan/positions rows with P&L %; safety key-values;
  activity; diary in `<details>`. Geist / Geist Mono fonts with system fallbacks. Light + dark tokens.
  Empty-chart text explains it fills as the Robot checks. Republished to the Artifact (v4).
- **Robot** saves `equity_history` (last 400 `[time, equity]` points) in `state.json` to feed the chart.
- **Telegram:** `robot/telegram.py` gained `card()` (HTML: bold title, lines, grey footer; `**x**` → bold;
  all text escaped) and a CLI `python -m robot.telegram "Title" "line" ...`. The Robot sends **one card per
  check** instead of one text per event. All 4 routine prompts now use the CLI with example layouts.
- Two lessons promoted to global rules 1.45.0 (cloud routines; file:// previews).

## Files Changed

| File | Change |
|---|---|
| `robot/dashboard.py` | New broker-style HTML render; safety rows show money/readable time |
| `robot/main.py` | `equity_history` in state; one Telegram card per check |
| `robot/telegram.py` | `card()`, `as_html` flag, CLI |
| `routines/plan.md`, `adjust.md`, `report.md`, `weekly.md` | Telegram via `robot.telegram` with templates |
| `tests/test_main.py` | equity history cap; one card per check |
| `tests/test_dashboard.py` | value + week change |
| `tests/test_io.py` | card escaping/bold; parse_mode HTML |
| `notebook/state.json` | reset to `{}` |
| `CLAUDE.md`, `CHANGELOG.md` | status, decisions, routines, environment notes |
| `~/.claude/CLAUDE.md`, `CHANGELOG.md`, `VERSION` | 1.45.0 |
| `~/.claude/.claude/launch.json` (untracked) | `trading-mc-preview` repointed to this session's scratchpad |

## How It Was Verified

- **New account:** Claude in Chrome (own tab) showed PA3ILFRGT at $1,000.00; GitHub secrets page showed both
  `APCA_*` updated 11/6/2026.
- **Keys work:** manual `robot` dry run → log "market closed" (`/v2/clock` needs valid keys).
  **Not proven:** that they're the *new* account's keys. That shows at the first market-hours check
  (`week_start_equity` must be 1000).
- **Environment:** reopened its settings: "Limited · 10 domains", "Setup script 3 lines", "7 variables".
- **Routines:** `RemoteTrigger` update responses show `mcp_connections: []` for all 4.
- **Plan run:** `get_run_log` read in full; commit 191af77 seen via `git fetch`.
- **Tests:** 73/73 (74/74 after the later dark-mode change). Verify-the-verifier: removing the equity cap → red; renaming `telegram.card` in main →
  red (it was green before `test_one_telegram_card_per_check` existed, i.e. the path had been untested).
- **Dashboard:** sample notebook rendered and served via `launch.json` http.server; Browser pane at 375 px
  (scrollWidth 375 = no sideways scroll) and desktop, light and dark, console clean. Scrub moved the hero
  to $1,028.48 / 11-10 10:30 and reset on leave. Empty state checked with the real notebook. Live Artifact
  v4 opened in Chrome.
- **Not verified:** Telegram HTML cards on a real phone (only mocked); setup script (first used by the
  next run); breadth CSV now reachable.

## Decisions Made

See CLAUDE.md Important Decisions (2026-11-06 rows):
- New $1,000 account rather than an "act as $1,000" setting.
- Own environment with plain env vars, because network secrets can't fit these APIs.
- Connectors cleared.
- Original broker-style design rather than a Robinhood copy.
- One Telegram card per check.

## Bugs Fixed

- **Stale weekly baseline.** Switching accounts would have read −99% and paused buying. Root cause:
  `week_start_equity` only resets on a new ISO week. Fix: reset `state.json`.
- **First Plan run had no market-breadth data and missing packages.** Root cause: the host wasn't
  allowlisted and the cloud image lacks the packages. Fix: domain + setup script (pending proof).

## Issues Remaining

- Prove the GitHub keys are the new account's, then Ethan deletes the old $100k paper account.
- Prove the setup script and breadth host work in the 12:30 ET Adjust run.
- See a real Telegram card on Ethan's phone.
- Before live, unchanged: fill-price exits, cash vs open orders, the "Paper money" badge.
- Parked: sleeve price-0 crash; repeating ❌ events.
- Cron is set for EST. Move every routine 1 hour earlier when DST starts on 2027-03-14.

## Next Steps

1. `git pull`; read `notebook/state.json`: `week_start_equity` should be 1000, with `equity_history` points.
   If yes, tell Ethan to delete PA3FRQ58C.
2. `RemoteTrigger list_runs` for Adjust/Report → `get_run_log`: no pip installs, breadth analyzer ran,
   Telegram card sent.
3. Ask Ethan how the cards and the new Mission Control look on his phone; adjust.
4. Watch for the first paper buy on a green/yellow day.

## Important Context

- Ethan pastes Telegram texts elsewhere. He wants them short and scannable.
- He confirmed "done"/"made it" steps honestly this session, but every step was still checked in Claude's
  own tab.
- He asked for a Robinhood look. Claude built an original broker-style design and said so.

---

# Session 2 — 2026-11-06 — README, research upgrade, scoreboard

**Branch:** `docs/readme`, `docs/research-upgrade-spec`, `feat/scoreboard`, `fix/same-day-clash` (all merged into `main` and deleted)

## Goals

Ethan asked for a plain-language explanation of how the bot researches, buys and sells; then a
README holding it plus the Mission Control link; then "as much research as possible before buying",
including a "time machine" that makes thousands of predictions. He handed the design choices to
Claude: "do what you think will perform best… we'll test it out."

## Completed

- `README.md`: plain-language guide (market light, screeners, research checks, sizing example,
  sell rules, safety brake, real-money rule) + Mission Control link + scoreboard section.
- Design spec `docs/superpowers/specs/2026-11-06-research-upgrade-design.md`: 3 pieces in order —
  (1) scoreboard, (2) per-stock history + odds, (3) extra layers, each kept only if the scoreboard
  shows it helps. Plan `docs/superpowers/plans/2026-11-06-scoreboard.md`. **Piece 1 built.**
- `backtest/` (stdlib only): `data.py` (Yahoo daily bars, past S&P 500 members from fja05680/sp500
  (MIT), cache in gitignored `backtest/cache/`, 27 renamed tickers mapped), `indicators.py`,
  `market.py` (light from prices + top-10% leaders), `rulebooks.py`, `engine.py`, `report.py`,
  `run.py` (`python -m backtest.run [--final] [--refresh]`).
- `safety.exit_reason`: the Robot's sell order in one function shared by the Robot and the replay.
- Live fix (Ethan said "Yes, fix it"): the Robot never buys below the 20-day average; `robot/research.py`
  DROPs those; `routines/plan.md` updated.
- Results in `backtest/results/2026-11-06-report.md` (before tuning) and `-final.md` (after tuning + the
  one-time 2024→today exam).

## Results (pretend $1,000 each period)

| Rulebook | 2019–2023 | 2024→today |
|---|---|---|
| Hold SPY | $2,062 (worst −34%) | $1,602 (worst −19%) |
| D. SPY only above its 200-day | $1,511 | $1,372 |
| B. Leaders on a dip, sell below 50-day | $1,288 | $1,284 |
| A. Today's bot | $968 | $1,203 |
| A+. Today's bot fixed, sell below 50-day | $1,241 | $955 |
| C. Leaders on a breakout, sell below 50-day | $1,023 | $1,015 |

Nothing passed the pass mark. B is the most consistent (profitable both periods; backtest-expert
"DEPLOY" on the tune years). A flipped from losing to winning between periods: unreliable. The
Careful limits keep only about 2.5 small positions open on average (about a third of the money
invested), which caps returns versus 100%-invested SPY.

## Files Changed

| File | Change |
|---|---|
| `README.md` | new: guide, Mission Control link, scoreboard section, buy step 4 |
| `backtest/*` | new: the scoreboard |
| `backtest/results/2026-11-06-{report,final}.md` | new: results |
| `robot/safety.py` | `exit_reason` added |
| `robot/main.py` | exits use `exit_reason`; buy skipped below 20-day average |
| `robot/research.py` | DROP below 20-day average |
| `routines/plan.md` | DROP reasons list the 20-day average |
| `tests/test_backtest.py` | new (14 tests) |
| `tests/test_safety.py`, `test_main.py`, `test_research.py` | exit order, buy guard, research DROP |
| `.gitignore` | `backtest/cache/` |
| `docs/superpowers/specs/…research-upgrade-design.md`, `plans/…scoreboard.md` | new |
| `CLAUDE.md`, `CHANGELOG.md` | status, rules, decisions, notes |

## How It Was Verified

- Full suite: 91 tests pass (`python -m unittest discover -s tests`), run again after each merge into `main`.
- `exit_reason` move: the new test failed before the function existed; all existing Robot tests pass unchanged.
- No future data: a test compares each indicator computed on a prefix with the full series; proven by
  making `sma20` peek one day ahead → the test failed; restored from a copy → it passes.
- Engine: a hand-worked trade (fill 9.8098, half at 11.988, rest at 9.4905 through a gap) matches to the
  cent; a gap below the stop never buys.
- Data: SPY replay $1,000 → $2,062 over 2019–2023 matches SPY's real return (about double with dividends);
  Yahoo history checked for AAPL/SPY; each renamed ticker checked to have history from 2018-01-02.
- Live guard: new tests failed first, then passed; fix confirmed in `origin/main:robot/main.py`.
- **Not verified:** the guard on a real paper trade (no buy yet: red light), and a local dry run (no
  Alpaca keys on this PC). The `tests.yml` run on GitHub wasn't checked (`gh` isn't installed and the
  repo is private).

## Decisions Made

- Scoreboard first, then per-stock checks, then layers: without a scoreboard, added research can't be
  shown to help. Rejected: layers first.
- Mechanical twin, not Claude: replaying Claude for every day would use up the Pro allowance. Rejected:
  Claude on a 20-day sample.
- Pass mark (set before any numbers): return ÷ worst drop beats SPY, no more than 2 points/year behind,
  at least 100 trades. Rejected: "makes money at all".
- Yahoo instead of Alpaca `feed=sip`: no Alpaca keys on the PC. Earnings not modelled: a gap-based guess
  would look like a rule without being one.
- `manifoldbt-backtester` rejected: one symbol, one entry rule, license restrictions.
- 50-day sell line chosen on the tune years only. The 2024→today exam was run once and is now **used**.
- Live buy guard uses strict `price < avg20` to match the exit's `price < avg20` exactly.

## Bugs Fixed

- Same-day round trips in the live bot → the bot could buy under the 20-day average and the 4 PM rule
  sells anything under it → the Robot skips those buys, research DROPs them.
- Download crash (`KeyError`) on bought-out tickers → Yahoo returns an empty shell, not a 404 → treated
  as no data (test added).
- 27 renamed companies missing → old tickers 404 → `RENAMED` map (same company only; buyers excluded).

## Issues Remaining

- 54 companies have no free history (bought out or bust); listed in each report. Some survivorship bias remains.
- Replay limits: daily bars, no earnings, no Claude, brake auto-reset on the Monday.
- Pieces 2–3 not built. Waiting on Ethan's direction.

## Next Steps

1. The paper-test checks from session 1's Next Steps.
2. Explain the 3 options from the results to Ethan in plain words (keep / switch to B / lean on SPY). His call.
3. If he picks B: change the morning plan's screeners and the Robot's 20-day sell line to 50-day, with his OK.
   Judge it on paper results (the exam is used).

## Important Context

- Ethan doesn't know trading terms. Use plain words, small tables and analogies ("flight simulator").
- He wants best-performing, not a specific tool: "don't just prioritize… the one skill I mentioned."
- `python -m backtest.run` takes about 1 minute after the first ~20-minute download (Yahoo is slow
  after about 1,000 requests; two downloaders working from opposite ends of the list halved it).
