# trading-agent — Design

**Date:** 2026-11-05 · **Status:** approved in chat (Parts 1–4), awaiting Ethan's review of this document
**Owner:** Ethan · **Repo:** private `ethan08madar-web/trading-agent`

---

## 1. What this is

A swing-trading assistant for a small account (under $1,000 real money later). Claude does the
research and writes a daily trade plan. A simple rules program (the **Robot**) follows the plan,
watches prices every 15 minutes, and enforces the safety rules in code.

It starts with **one week of paper (fake) money**. That week tests whether the machine works,
not whether the strategy makes money. One week is far too short to judge profit.

Nobody can predict the market. No profit is promised. The rules below are Ethan's choices.
Claude explains options and does not give personalised investment advice.

### Hard limit

Claude, and any agent Claude starts, **never places real-money trades**. In live mode the Robot
has **no order code path at all**. It sends Telegram alerts, and Ethan places every real trade
himself in the Alpaca app. This is settled and is not to be reopened.

---

## 2. Architecture: a team of two

```
            ┌──────────────── Notebook (this GitHub repo) ────────────────┐
            │  settings.yaml · plan/ · state.json · trades.jsonl · diary/  │
            └──────▲─────────────────────────────────────────────▲─────────┘
                   │ writes plan, diary                           │ writes state, trades
                   │ reads state, trades                          │ reads plan, settings
   ┌───────────────┴──────────────┐               ┌───────────────┴──────────────┐
   │ Claude (brain)               │               │ Robot (hands)                │
   │ Claude Code cloud routine    │               │ Python on GitHub Actions     │
   │ 3 runs / weekday + weekly    │               │ every 15 min, market hours   │
   └───────┬───────────────┬──────┘               └───────┬───────────────┬──────┘
           │               │                              │               │
     Mission Control   Telegram                        Alpaca          Telegram
     (Artifact page)                                (paper orders)
```

Claude and the Robot **never talk directly**. They only communicate through files in the
Notebook. Each one writes only its own files, so they never edit the same file.

| Part | Runs on | When | Cost |
|---|---|---|---|
| Claude | Claude Code cloud scheduled routine, Ethan's **Pro** plan | 09:00 plan · 12:30 adjust · 16:30 report (ET, weekdays); weekly review on the weekend | Counts against the Pro allowance. Kept to about 3 runs a day so other projects aren't blocked. Minimum interval is 1 hour. |
| Robot | GitHub Actions cron | Every 15 min, weekdays | Free tier: 2,000 Actions minutes a month for a private repo (budget in §8) |
| Notebook | This private repo | — | free |
| Broker | Alpaca (paper first) | — | free |
| Alerts | Telegram bot | — | free |

**Rejected alternatives**
- **Claude alone, every hour:** uses up the Pro allowance and only checks hourly.
- **Everything on Ethan's PC:** stops whenever the PC is off.

---

## 3. Components

### 3.1 Claude routines (`routines/`)

There is one prompt file per run, and the cloud routine reads it. The 74 installed skills
(`.claude/skills/`) do the research.

| Run | Reads | Does | Writes |
|---|---|---|---|
| **Plan** 09:00 ET | settings, state, trades, yesterday's diary | Sets the market light (e.g. `market-breadth-analyzer`, `market-environment-analysis`). Screens for swing candidates. Skips stocks with earnings in the next 3 trading days. Runs `data-quality-checker`. Picks entry, stop and target for each pick, with a one-line reason. | `plan/YYYY-MM-DD.json`, Telegram 📋, Mission Control |
| **Adjust** 12:30 ET | plan, state | Re-checks the light, cancels picks that broke down, tightens stops. Flags a missing heartbeat. | the same plan file (bumps `version`), Mission Control |
| **Report** 16:30 ET | everything | Diary entry, P&L, safety meter, FMP calls used | `diary/YYYY-MM-DD.md`, Telegram 📓, Mission Control |
| **Weekly** (weekend) | the week | Review (`trade-performance-coach`, `signal-postmortem`) | `diary/week-YYYY-WW.md`, Mission Control |

Claude **suggests** trades. It does not enforce limits. Every limit is enforced again by the Robot.

### 3.2 Plan file format (`plan/YYYY-MM-DD.json`)

```json
{
  "date": "2026-11-09",
  "version": 1,
  "market_light": "green",
  "trend_sleeve": { "hold_spy": true },
  "picks": [
    { "symbol": "AAPL", "entry_max": 231.50, "stop": 224.00, "target": 246.00,
      "reason": "Pullback to 20-day average in an uptrend" }
  ],
  "cancel": ["MSFT"],
  "light_falling": false,
  "sell_earnings": ["NVDA"],
  "stops": { "NVDA": 118.00 },
  "fmp_calls": 37
}
```

- `light_falling`: true means yellow allows 0 new positions.
- `sell_earnings`: held stocks with earnings within 2 days. Claude finds these, and the Robot
  sells them, so the Robot never needs FMP.
- `stops`: tighter stops for held stocks. The Robot only ever **raises** a stop.
- `fmp_calls`: Claude's estimate, shown on Mission Control.

The Robot validates this file. If it is missing, malformed, from an old date, or breaks the
schema, it counts as **no plan** (see §5). Claude self-checks with
`python -m robot.plan <file> <date>` before pushing.

### 3.3 Robot (`robot/`)

Small modules, one job each:

| File | Job |
|---|---|
| `robot/main.py` | One check: load → check clock → manage exits → place entries → save → alert. |
| `robot/settings.py` | Loads and validates `settings.yaml`, including the `mode: paper \| live` setting. |
| `robot/safety.py` | **Pure functions**: position size, the risk checks, and the circuit breaker. No network calls, fully unit-tested. |
| `robot/broker.py` | Read-only Alpaca calls: clock, account, positions, latest prices. |
| `robot/paper_orders.py` | The **only** file that can place orders. The URL `https://paper-api.alpaca.markets` is hardcoded in it, not a setting. It is imported only when `mode == paper`. |
| `robot/telegram.py` | Sends messages. If sending fails, it logs and carries on, never crashes. |

**One check, step by step**
1. Ask Alpaca's clock whether the market is open. If it's closed, exit. The cron runs the
   whole 13:00–21:59 UTC window, so daylight-saving changes don't matter.
2. Load settings, the plan, state and positions.
3. **Exits first**, for every position:
   - Stop hit → sell.
   - Closes below its 20-day average → sell. This is checked at the last check after 15:45 ET.
   - Earnings within 2 days → sell.
   - Target hit → sell half and move the stop to the entry price.
   - Trend sleeve: sell SPY when it closes below its 50-day average.
   - Stops on whole shares are real stop orders at Alpaca. Fractional shares can't have
     broker-side stops, so the Robot checks those at every run.
4. **Entries**, only when every check in `safety.py` passes (§4). Each entry is a
   limit buy at `entry_max`, valid for the day.
5. Write `state.json`, add lines to `trades.jsonl`, commit and push, send Telegram ✅/❌/🛑/⏸️.

**Live mode:** steps 3–4 send Telegram alerts instead of placing orders, for example
"Plan says buy 3 AAPL ≤ $231.50, stop $224.00". `paper_orders.py` is never imported.
A unit test fails if any live-mode code path imports it or contains an order call.

### 3.4 Notebook files

All files live under `notebook/`.

| File | Written by | Contents |
|---|---|---|
| `settings.yaml` | Ethan (Claude edits only when he asks) | mode, risk limits, `breaker_reset` counter |
| `plan/YYYY-MM-DD.json` | Claude | §3.2 |
| `diary/*.md` | Claude | daily and weekly reports |
| `state.json` | Robot | positions, stops, `last_check` (the heartbeat), loss streak, week P&L, `paused` |
| `trades.jsonl` | Robot | one line per order or fill or alert |

To avoid two writers pushing at once: each side writes only its own files and runs
`git pull --rebase` before every push. The Robot's Actions workflow uses a `concurrency`
group, so only one check runs at a time.

### 3.5 Mission Control

A private claude.ai Artifact page, republished at the end of every Claude run. It is **not**
live every 15 minutes. An always-on server (about $5 a month) is a later upgrade if wanted.

It shows:
- what's happening now, the time of the Robot's last check, and the next run
- the market light
- today's plan with the reasons
- open positions and P&L
- trades waiting and done
- the safety meter: risk used, loss streak, paused or not
- an activity feed, the diary, and FMP calls used out of 250

**Unproven:** whether a cloud routine can republish an Artifact. This is setup step 5, tested
before anything is built around it. **Fallback:** a static page built into the repo and
served by GitHub Pages. Note that GitHub Pages on a private repo needs a paid GitHub plan,
so the fallback may instead be a Markdown dashboard file in the repo.

### 3.6 Telegram messages

📋 plan ready · ✅/❌ trade done or failed (fake money in the test) · 🛑 stop hit · ⏸️ circuit breaker paused · 📓 daily report · ⚠️ problem

---

## 4. Safety rules (the "Careful" set, enforced in `safety.py`)

| Rule | Value |
|---|---|
| Max loss per trade if the stop hits | 1% of account equity |
| Max open positions | 4 (trend sleeve included) |
| Max in one position | 30% of account equity |
| Circuit breaker | No new buys after −5% in a calendar week, or after 3 losing trades in a row. Ethan resets it by raising `breaker_reset` by 1 in `settings.yaml`. |
| Market light | 🟢 up to 4 positions · 🟡 up to 2, and nothing new if the light is turning down · 🔴 no new buys |
| Trend sleeve | Hold SPY (at most 30%) when the light is green and SPY is above its 50-day average |
| Earnings | Don't buy with earnings within 3 trading days; sell with earnings within 2 days |

**Position size** = `min( floor_to_0.01( 1% equity / (entry_max − stop) ), 30% equity / entry_max )`
shares, also capped by available cash. If the result is 1 share or more, it is rounded down
to whole shares so a broker stop order can be placed. Below 1 share, it is fractional, rounded
down to 0.01.

`settings.yaml` can make these limits **stricter, never looser**. The code refuses a file with
risk > 1%, a position > 30%, more than 4 positions, a weekly limit > 5%, or a loss streak > 3. A pick is rejected if
`stop >= entry_max`, if the stop is more than 15% below entry, or if the size works out to zero.

---

## 5. When something breaks: play safe

| Failure | What happens |
|---|---|
| The Robot crashes or can't reach Alpaca | No trades. Telegram ⚠️. Tries again at the next 15-minute check. |
| No valid plan today (the Claude run failed, or the file is bad) | No new buys. The Robot still manages stops and exits. |
| Data looks wrong (`data-quality-checker`, or a price of 0 or missing) | Skip that stock. |
| Telegram is down | Everything is still in `trades.jsonl` and `state.json`. |
| Free FMP limit (250 calls a day) reached | Skip those skills for the day and say so in the report. |
| Heartbeat: `last_check` is over 1 hour old during market hours | Claude's next run flags it ⚠️ (Telegram + Mission Control). GitHub can delay or skip cron runs when it's busy, and this catches that. |
| Push conflict | Rebase and retry once. If it still fails, ⚠️ and keep the state locally until the next run. |

---

## 6. Testing

- **`safety.py`:** unit tests with Python's built-in `unittest` (no extra framework). Cover
  sizing, every limit, the circuit breaker, a bad stop, and a size of zero. Break one check
  on purpose to see the test fail before trusting it.
- **Plan validation:** good file, missing file, old date, and bad fields → treated as no plan.
- **Live-mode guard:** a test that fails if live mode can reach `paper_orders.py` or any
  order call.
- **Dry run:** `python -m robot.main --dry-run` does everything except orders and pushes,
  run against the paper account.
- **End to end:** one manual Actions run during market hours on paper, before the test week.

---

## 7. Rollout

### 7.1 Setup (Ethan does these, one step per message)
1. Alpaca **paper** account and its 2 keys.
2. FMP **free** key.
3. Telegram bot (BotFather) and chat ID.
4. Ethan pastes the keys into GitHub Actions secrets and Claude cloud environment secrets.
   The cloud environment needs **Custom** network access listing the Alpaca, FMP, Telegram
   and Yahoo hosts; the Trusted setting blocks them. Keys never go in chat.
5. Spike: can a cloud routine republish the Mission Control Artifact? (§3.5)

### 7.2 Test week (5 market days, paper)
The report card at the end:
- a plan every morning
- no Robot gap over 1 hour
- **zero** safety-rule breaks
- FMP calls used, and whether hitting the limit cost anything important. This decides
  whether the paid plan (about $30 a month) is worth it.
- trades and fake P&L, for interest only

### 7.3 Moving to real money (Ethan's choice)
- The bar is safety, not profit: zero rule breaks and zero missed heartbeats.
  Recommended: 2–4 more paper weeks first.
- Ethan funds his live Alpaca account himself (under $1,000) and sets `mode: live`.
- The Robot then only alerts. Ethan places every trade in the Alpaca app.
- **Open question:** the live Robot needs to *read* positions to warn about stops. Check
  whether Alpaca offers read-only keys. If it doesn't, the guard is the absence of order code
  plus the §6 live-mode test.

---

## 8. Limits and budgets

- **GitHub Actions minutes:** about 36 checks a day × 22 days ≈ 790 runs. Each run is
  billed at a minimum of 1 minute, so expect about 800–1,600 minutes out of 2,000.
  Keep runs short: cache pip, and exit at once when the market is closed. If it gets tight,
  move to a 20-minute interval.
- **Pro allowance:** 3 runs a weekday plus 1 on the weekend. Don't add more without Ethan.
- **FMP free tier:** 250 calls a day. Count every call and show the total on Mission Control.

## 9. Not in v1

- An always-on server for live updates
- Any automatic real-money orders (never)
- Short selling and options
- Finviz Elite skills (optional, paid)
