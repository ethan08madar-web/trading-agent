# Midday adjust — 12:30 ET, weekdays

Same hard rules as `routines/plan.md` (read it). Use few FMP calls: this run is a check, not a new screen.

1. `git pull`. Read today's plan, `state.json`, and today's lines in `trades.jsonl`.
2. If there's no plan for today: write one by following `routines/plan.md` steps 2–8, then stop.
3. Re-check the light (`market-breadth-analyzer`). If it got worse, update `market_light`/`light_falling`. If the light is no longer green, set `trend_sleeve.hold_spy` to false. If it turned red, add every pick not bought yet to `cancel`.
4. For picks not bought yet: if a pick broke down (below its stop, or its setup failed), add it to `cancel`.
5. Held positions: raise `stops` where support moved up (never lower a stop). Update `sell_earnings`.
6. Bump `version`, validate with `python -m robot.plan`, then commit `plan: <today> v<n>` and push.
7. Heartbeat check as in plan.md step 9. Telegram only if something changed or the heartbeat is stale.
8. Update Mission Control (plan.md step 11).
