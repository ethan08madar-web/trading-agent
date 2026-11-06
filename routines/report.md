# Daily report — 16:30 ET, weekdays

Same hard rules as `routines/plan.md`. No FMP calls needed.

1. `git pull`. Read today's plan, `state.json`, today's lines in `trades.jsonl`, and `settings.yaml`.
2. Write `notebook/diary/<today>.md` in plain, simple English:
   - Market light and why (one line).
   - What the Robot did today: orders, fills, stops hit, sales — copied from `trades.jsonl`, not invented.
   - Open positions: entry, stop, last price, profit/loss in $ and % (paper money).
   - Safety meter: losses in a row, week change vs `week_start_equity`, paused or not.
   - Problems: missing plan, stale heartbeat, FMP limit, Telegram failures.
   - FMP calls used today (estimate).
   - Say plainly: one day of results says nothing about whether the strategy works.
3. Commit `diary: <today>` and push.
4. Telegram with `python -m robot.telegram` (see plan.md step 10), e.g.:
   `"📓 Daily report — Fri Nov 6" "**Account:** \$1,012.40 (▲ +\$12.40 today)" "**Trades:** bought NVDA; AMD stop hit" "**Open:** 2 positions" "" "<one plain-English sentence on the day>" "" "Mission Control: <Artifact URL>"`
5. Update Mission Control (plan.md step 11).
