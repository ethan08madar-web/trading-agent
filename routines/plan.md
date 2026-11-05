# Morning plan — 09:00 ET, weekdays

You are the research half of trading-agent. First read `CLAUDE.md` and
`docs/superpowers/specs/2026-11-05-trading-agent-design.md`.

## Hard rules
- Never place, change or cancel orders. Never call any URL containing `/v2/orders`. The Robot does that.
- Never edit `notebook/settings.yaml`, `notebook/state.json` or `notebook/trades.jsonl`.
- Write only `notebook/plan/<today>.json` and Mission Control. Never write keys or tokens anywhere.
- Free FMP plan: at most ~200 FMP calls per day across all runs. Count your FMP-using script runs.

## Steps
1. `git pull`. Read `notebook/settings.yaml`, `notebook/state.json`, the last 50 lines of
   `notebook/trades.jsonl`, and the newest file in `notebook/diary/`.
2. Market light: run `market-breadth-analyzer`, plus `uptrend-analyzer` or `market-top-detector` if
   calls allow. Choose `green`/`yellow`/`red` and `light_falling` (true if breadth is weakening).
3. If red → no picks. Otherwise find up to 6 swing candidates with `vcp-screener`,
   `canslim-screener` or `stockbee-momentum-burst-screener`, then for each:
   - `earnings-calendar`: drop it if earnings are within 3 trading days.
   - `data-quality-checker`: drop it if the data looks wrong.
   - `technical-analyst`: entry_max (the highest price worth paying), stop (below support;
     within 15% of entry), target (at least 2× the risk).
   - Keep the best 4, ordered best first, each with a one-line `reason`.
4. Held positions (`state.json` → `positions`):
   - earnings within 2 days → put it in `sell_earnings`
   - a better stop (higher only) → put it in `stops`
5. Trend sleeve: `"hold_spy": true` only if the light is green and SPY is above its 50-day average.
6. Write `notebook/plan/<today>.json` (today = America/New_York date):

```json
{"date": "YYYY-MM-DD", "version": 1, "market_light": "green", "light_falling": false,
 "trend_sleeve": {"hold_spy": true},
 "picks": [{"symbol": "AAPL", "entry_max": 231.50, "stop": 224.00, "target": 246.00, "reason": "..."}],
 "cancel": [], "sell_earnings": [], "stops": {}, "fmp_calls": 0}
```

7. Run `python -m robot.plan notebook/plan/<today>.json <today>`. It must print `OK`. Fix and repeat until it does.
8. Commit `plan: <today>` and push to `main` (on a conflict: `git pull --rebase`, then push).
9. Heartbeat: if it's a weekday during market hours and `last_check` in `state.json` is over 1 hour
   old, say so in the Telegram message: "⚠️ Robot hasn't checked in since <time>".
10. Telegram (bot token and chat id are in the environment): send
    "📋 Plan ready: <light> — <N> picks: AAPL, …". One message.
11. Mission Control: `python -m robot.dashboard > mission-control.html` and publish it to the
    Mission Control Artifact (same URL every time; see CLAUDE.md). If publishing fails, commit
    `python -m robot.dashboard --markdown > notebook/MISSION_CONTROL.md` instead.
