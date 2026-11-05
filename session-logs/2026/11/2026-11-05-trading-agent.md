# Session — 2026-11-05 — trading-agent

**Date:** 2026-11-05
**Project:** trading-agent
**Branch:** main

## Goals

Ethan wants an AI stock-trading agent with Claude as the "mastermind", based on
https://www.mindstudio.ai/blog/build-ai-trading-agent-claude-code-alpaca. Started as a side session of another session.

## Completed

- Read the guide and explained it (Claude Code + Alpaca + Python scripts; MindStudio not needed).
- Checked `C:\Users\ethan\Claude\stocktrader`: only an Aug 2026 design/plan for a mock React app. Ethan said leave it alone; new folder instead.
- Ethan asked for real money. Told him plainly: Claude (or any agent Claude starts) will not place real-money trades, even with his keys/permission. Offered alternatives; he accepted a design where a rules Robot runs and he places live trades himself.
- Downloaded + safety-reviewed + installed all 74 skills from `tradermonty/claude-trading-skills` (MIT, commit d8e71ce) into `.claude/skills/`. Installed Python deps (user site).
- Brainstorming (architectural path): Ethan's answers — swing trades + small trend sleeve; under $1,000 real later; Careful risk limits; Telegram; Pro plan; paper week where Robot trades fake money; Mission Control private web page; Way 2 "team of two". Design Parts 1 and 2 approved.

## Files Changed

| File | Change |
|---|---|
| `.claude/skills/*` (74 skills) + `LICENSE-claude-trading-skills` + `SOURCE.txt` | Added |
| `.gitignore` | `.env*` (except `.env.example`), `state/`, pycache |
| `CLAUDE.md`, `CHANGELOG.md`, this log | Added |
| `~/.claude/skills/trader-memory-core`, `~/.claude/skills/signal-postmortem` | Added globally earlier (outside this repo); deletion blocked by safety check |

## How It Was Verified

- Skill safety: grepped all non-test Python for hosts contacted (FMP, Finviz, Alpaca, SEC, CME, Yahoo, etc.), order-placement calls (none found — `/v2/orders|submit_order|place_order|...` → zero hits), eval/exec/shell=True/pickle (none), subprocess users (read each: `claude` CLI, `uv`, opening a browser URL, MT5 tester).
- Alpaca code in skills only reads account/inventory (`portfolio-manager/check_alpaca_connection.py`, parabolic-short adapters).
- `trader-memory-core`: `thesis_store.py --state-dir <tmp> list` → `[]` exit 0; bogus command → exit 2 (check can fail).
- `market-breadth-analyzer` ran on live data → Composite 48.8/100, Neutral, exit 0.
- Pro-plan cloud task facts came from a docs lookup (code.claude.com/docs/en/routines.md, cloud-environments.md): min interval 1 hour, runs count against Pro usage, Trusted network blocks Alpaca/Telegram/Yahoo (need Custom), network secrets for keys.
- **Not verified:** that a cloud scheduled task can republish an Artifact (docs suggest yes); the ~85 skills' own test suites were not run; opencv/manifoldbt deps not installed (only needed by niche skills).

## Decisions Made

See CLAUDE.md Important Decisions table. Key: Way 2 team-of-two (rejected all-Claude hourly — burns Pro and slower; rejected PC-only — stops when PC off). Live Robot has no order code at all.

## Bugs Fixed

- Skill download loop: every `curl` failed → Python on Windows printed paths with `\r\n`, so `while read p` kept a trailing CR in URLs → `tr -d '\r'` fixed it.
- `thesis_store.py` "No module named yaml" though installed → `python -I` disables user site-packages where `pip --user` put it → run without `-I` for installed skills.

## Issues Remaining

- Design Part 3 was drafted but **not shown** to Ethan (he left for a workout). Draft below.
- Part 4 not drafted: test week plan, how to go to real money, Ethan's one-step-at-a-time setup (GitHub private repo, Alpaca paper keys, FMP free key, Telegram bot).
- ~~No GitHub remote~~ Done after wrap-up: private repo `ethan08madar-web/trading-agent` created in Chrome, pushed, unauthenticated API → 404 (private). Duplicate global skill copies deleted with Ethan's OK. Global rules 1.42.0: new projects always get a private repo; two Windows gotchas.
- Spec + implementation plan not written.

### Part 3 draft (show Ethan next)

**Mission Control page** (private claude.ai Artifact, refreshed at each Claude run): status now + last Robot check time + next run; market light; today's plan with reasons; open positions & P&L (paper); trades waiting/done; safety meter (risk used, loss streak, paused?); activity feed; diary; FMP calls used vs 250.
**Telegram:** 📋 plan ready · ✅/❌ trade done (fake) · 🛑 stop hit · ⏸️ circuit breaker paused · 📓 daily report · ⚠️ problem.
**When something breaks:** Robot fails or can't reach Alpaca → no trades, ⚠️ Telegram, retry next 15 min. Claude run fails/missing plan → Robot trades nothing new, only manages stops. Data looks wrong (`data-quality-checker`) → skip. Telegram down → still logged in Notebook. FMP quota hit → skip those skills that day, say so in report. Heartbeat: if no Robot check for 1 hour during market hours, Claude's next run flags it.

## Next Steps

1. Show Part 3, then Part 4; get approval each.
2. Write spec to `docs/superpowers/specs/2026-11-0X-trading-agent-design.md`, self-review, Ethan reviews.
3. Ask Ethan to OK creating a private GitHub repo; then push.
4. writing-plans → build.

## Important Context

- Ethan prefers simple language and one manual step per message. He wants it "very advanced"; he was told honestly that nobody can predict the market and no profit is promised.
- He asked several times for Claude to press the real button (directly or via an agent) — the answer is always no; don't reopen it.
- Pro plan: keep Claude runs to ~3/day so his other projects aren't blocked.
- The originating session's brief said "paper first, never real money"; Ethan later said he wants real money after the paper week — live mode = alerts only, he trades.
