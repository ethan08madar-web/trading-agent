# Weekly review — Saturday

Same hard rules as `routines/plan.md`.

1. `git pull`. Read this week's diaries, plans and `trades.jsonl` lines.
2. Use `trade-performance-coach` and `signal-postmortem` on the week's closed trades.
3. Write `notebook/diary/week-<YYYY>-W<ww>.md`:
   - **Report card** (spec §7.2):
     - a plan every morning? (yes / no + dates)
     - any Robot gap over 1 hour? (from the gaps between `trades.jsonl` times and `state.json` history in git log)
     - any safety-rule break? (must be zero)
     - FMP calls vs 250 a day, and did the limit cost anything important?
     - trades and paper P&L, for interest only
   - What to keep or change (ideas only — Ethan decides; never edit settings.yaml).
   - Be honest: a week is far too short to judge profit.
4. Commit, push, then Telegram with `python -m robot.telegram` (see plan.md step 10):
   title "📊 Weekly review — week <ww>", then "**Week:** ▲/▼ \$X (Y%)", "**Trades:** N (W won, L lost)",
   "**Safety rules broken:** 0", one line on the biggest lesson, and the Mission Control link. Update Mission Control.
