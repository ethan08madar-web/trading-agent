# Morning plan — 09:00 ET, weekdays

You are the research half of trading-agent. First read `CLAUDE.md` and
`docs/superpowers/specs/2026-11-05-trading-agent-design.md`.

## Hard rules
- Never place, change or cancel orders. Never call any URL containing `/v2/orders`. The Robot does that.
- Never edit `notebook/settings.yaml`, `notebook/state.json` or `notebook/trades.jsonl`.
- Write only `notebook/plan/<today>.json`, `notebook/diary/*.md`, and Mission Control (`mission-control.html` is never committed; `notebook/MISSION_CONTROL.md` only as the fallback). Never write keys or tokens anywhere.
- Free FMP plan: at most ~200 FMP calls per day across all runs. Count your FMP-using script runs.
- `<today>` always means today's date in America/New_York.
- Plan, adjust and daily report runs only: if the US stock market is closed today (weekend or holiday — check Alpaca's clock/calendar), send nothing, commit nothing, and stop. The weekly review always runs.
- Never paste URLs, raw error output or API responses into any file or message — keys and tokens live inside URLs.
- Stage only the files you wrote, by path (never `git add -A` or `git add .`). Push with `git pull --rebase` then `git push`; if that fails, retry once. Only send a "ready" Telegram message after the push succeeded; if it didn't, send "⚠️ <plan/diary/review> not saved: push failed" instead.

## Steps
1. `git pull`. Read `notebook/settings.yaml`, `notebook/state.json`, the last 50 lines of
   `notebook/trades.jsonl`, and the newest file in `notebook/diary/`.
2. Market light: run `market-breadth-analyzer`, plus `uptrend-analyzer` or `market-top-detector` if
   calls allow. Choose `green`/`yellow`/`red` and `light_falling` (true if breadth is weakening).
3. If red → no picks. Otherwise find up to 6 swing candidates with `vcp-screener`,
   `canslim-screener` or `stockbee-momentum-burst-screener`. Note each one's pivot and stop
   if the screener gives them (`vcp-screener` does). Then check them all in one go — and add
   every held symbol to the same command for step 4:
   `python -m robot.research SYM1 SYM2 ...` (1 FMP call in total)
   - `DROP` lines: leave that stock out (earnings within 3 trading days — any company size —
     bad or missing price data, or earnings unknown because FMP is unreachable). Don't
     second-guess a DROP.
   - `KEEP` lines give the last close, 20/50-day averages, 10-day low, 20-day high, and a
     default entry_max / stop / target. Use the screener's pivot and stop when it gives them;
     otherwise start from the defaults. You may raise the stop or lower entry_max, never the
     other way. Rules: stop below entry_max and within 15% of it; target at least 2× the risk.
     A KEEP marked "stop is over 15% below" needs a closer real support level, or drop it.
   - Do not use `earnings-calendar` (it skips companies under $2B), `data-quality-checker`
     (it checks written reports, not prices) or `technical-analyst` (it needs chart images)
     for this step.
   - Keep the best 4, ordered best first, each with a one-line `reason`.
4. Held positions (`state.json` → `positions`), from the same `robot.research` output:
   - earnings within 2 days → put it in `sell_earnings`
   - a better stop (higher only) → put it in `stops`
   - Any held position with `stop: null` in state.json must get a stop in `stops` today.
5. Trend sleeve: `"hold_spy": true` only if the light is green and SPY is above its 50-day average.
6. Write `notebook/plan/<today>.json` (today = America/New_York date):

```json
{"date": "YYYY-MM-DD", "version": 1, "market_light": "green", "light_falling": false,
 "trend_sleeve": {"hold_spy": true},
 "picks": [{"symbol": "AAPL", "entry_max": 231.50, "stop": 224.00, "target": 246.50, "reason": "..."}],
 "cancel": [], "sell_earnings": [], "stops": {}, "fmp_calls": 0}
```

7. Run `python -m robot.plan notebook/plan/<today>.json <today>`. It must print `OK`. Fix and re-run at most 3 times. If it still fails, do not commit a plan: send '⚠️ No plan today: <first problem line>' on Telegram and stop (the Robot then buys nothing and only manages exits).
8. Commit `plan: <today>` and push to `main` (on a conflict: `git pull --rebase`, then push).
9. Heartbeat: if it's a weekday during market hours and `last_check` in `state.json` is over 1 hour
   old, say so in the Telegram message: "⚠️ Robot hasn't checked in since <time>".
10. Telegram (bot token and chat id are in the environment): send
    "📋 Plan ready: <light> — <N> picks: AAPL, …". One message.
11. Mission Control: `python -m robot.dashboard > mission-control.html` and publish it to the
    Mission Control Artifact (same URL every time; see CLAUDE.md). If publishing fails, commit
    `python -m robot.dashboard --markdown > notebook/MISSION_CONTROL.md` instead.
