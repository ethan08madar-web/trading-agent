# trading-agent

> Project knowledge base. Global standards live in `~/.claude/CLAUDE.md` — do not repeat them here.

---

## 🟢 Start here

**New session? Do this before anything else:**

1. `git status` and `git log --oneline -5` — see what's uncommitted.
2. `git fetch` — report if the remote is ahead. Remote: private `github.com/ethan08madar-web/trading-agent`.
3. Read **Current Project Status** below.
4. Read the newest file in `session-logs/`.
5. Report back: current state, goal, priorities, blockers, and where the last session said to pick up. Then start.

**Finishing up?** Run `/wrap-up`.

---

## Current Project Status

- **Current Phase:** Built (plan Tasks 1–10, merged to `main` 2026-11-05). 58 tests pass. Not yet run against real Alpaca/Telegram — needs Ethan's accounts.
- **Current Goal:** Ethan's setup (plan Task 0 spike + Task 11), first real Actions run, then the 1-week **paper-money** test.
- **Current Priority:** Plan Task 0 — Ethan makes one Claude routine to test pushing to `main` and republishing the Mission Control Artifact.
- **Current Blockers:**
  - Unproven: can a Claude cloud routine push to `main` and republish an Artifact? (plan Task 0; fallback `notebook/MISSION_CONTROL.md`).
  - Ethan still has to create (himself, one step per message): Alpaca paper account + keys, FMP **free** key, Telegram bot, GitHub Actions secrets, cloud environment (plan Task 11).
  - Open: does Alpaca offer read-only keys for live mode (spec §7.3)?
- **Must fix before `mode: live`** (fine for paper): exit price from Alpaca FILL activities (now last-seen price); cash ignores open buy orders/margin; dashboard says "Paper money test" always.
- **Known, parked:** trend-sleeve buy crashes the check if the broker returns price 0 (fails safe, ⚠️ alert); a repeating ❌ "failed" order event is sent every check.
- **Recommended Next Task:** plan Task 0, then Task 11, one step per message.

*Last updated: 2026-11-05*

---

## Purpose

A swing-trading assistant for Ethan (small account, under $1,000 real money later). Claude does research and writes a daily trade plan; a simple Robot program follows the plan and watches prices. Week 1 is paper (fake) money only, to decide whether the paid FMP data plan is worth it.

## Business Rules

- **Hard limit:** Claude (and any agent Claude starts) never places real-money trades. Ethan was told this plainly and agreed to the design around it. In live mode the Robot has **no order code path at all** — it only sends Telegram alerts and Ethan places trades in the Alpaca app.
- Paper week: the Robot places **paper** trades itself (Ethan chose this).
- Risk limits ("Careful" set, chosen by Ethan) — enforced in code, not just prompts:
  - Max loss per trade if stop hits: 1% of account.
  - Max 4 positions; max 30% of account in one position.
  - Pause all new buys after −5% in a week or 3 losses in a row.
- Market light: 🟢 up to 4 positions · 🟡 up to 2, nothing new if turning down · 🔴 no new buys.
- Trend sleeve: hold SPY (≤30%) when light is green and SPY > 50-day average; sell when it closes below.
- Exits (defaults, Ethan can change): stop hit → sell; close below 20-day average → sell; earnings within 2 days → sell; target hit → sell half, move stop to entry.
- Skip stocks with earnings in the next few days.
- No personalised investment advice — rules are Ethan's choices; Claude explains options.

## Architecture (built 2026-11-05)

- **Claude (brain):** Claude Code cloud scheduled task, 3 runs/weekday — 9:00 plan, 12:30 adjust, 16:30 diary/report (ET); weekly review on weekends. Uses Ethan's **Pro** allowance (runs count against it; min interval 1 hour).
- **Robot:** Python on GitHub Actions cron, every 15 min while market is open. Reads the plan, checks prices, runs safety checks, places paper orders (paper week) / sends alerts (live), checks stops for fractional positions. Uses no Claude allowance.
- **Notebook:** one private GitHub repo — plan, trades, diary, settings. Claude and Robot only communicate through it.
- **Alpaca:** broker (paper first). Fractional shares can't have broker-side stops → Robot checks them every 15 min; whole shares get real stop orders.
- **Telegram:** live alerts. **Mission Control** Artifact page: refreshed on each Claude run (not live every 15 min — a ~$5/mo always-on server is the later upgrade if wanted).

## Integrations

| Service | Use | Credential | Cost |
|---|---|---|---|
| Alpaca | broker + market data | `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY` (some skills read `ALPACA_API_KEY`/`ALPACA_SECRET_KEY`) | free |
| FMP | data for 27 skills | `FMP_API_KEY` — free tier 250 calls/day for the test week | free / ~$30 mo |
| Finviz Elite | optional, 4 skills | `FINVIZ_API_KEY` | optional |
| Telegram | alerts | bot token + chat id | free |

Keys go in a gitignored `.env` (Ethan enters them himself) and as cloud network secrets / GitHub Actions secrets. Cloud environment needs **Custom** network access listing Alpaca, FMP, Telegram, Yahoo hosts (Trusted blocks them).

## Project Conventions

- Skills: all 74 from `tradermonty/claude-trading-skills` (MIT, commit d8e71ce) in `.claude/skills/` — see `.claude/skills/SOURCE.txt`. Project-scoped so they don't load in other projects.
- Python 3.12 (user site-packages). Don't run the skill scripts with `python -I` — it hides the `--user` packages.
- Example run: `python .claude/skills/market-breadth-analyzer/scripts/market_breadth_analyzer.py --output-dir <dir>`

## Roadmap

- [x] Install skills (74) and Python deps
- [x] Design Parts 1–4 → spec (2026-11-05)
- [x] Spec approved → implementation plan (2026-11-05)
- [x] Private GitHub repo (2026-11-05)
- [ ] Ethan's accounts (Alpaca paper, FMP free, Telegram)
- [x] Build Robot + Claude routines + Mission Control (2026-11-05)
- [ ] 1-week paper test → decide on FMP paid and real money

## Important Decisions

| Date | Decision | Why | Alternatives rejected |
|---|---|---|---|
| 2026-11-05 | New project folder `trading-agent`; `stocktrader` untouched | Ethan: stocktrader (Aug 2026 mock React app plan) is unrelated | Reusing stocktrader |
| 2026-11-05 | "Team of two": Robot (GitHub Actions, 15 min) + Claude (3 cloud runs/day) | Watches 4× more often than hourly Claude, protects Pro allowance for other projects, no PC needed | All-Claude hourly (burns Pro, hourly only); everything on PC (stops when PC off) |
| 2026-11-05 | Claude never presses real-money buy/sell; live Robot has no order code | Safety limit; Ethan asked repeatedly (incl. "tell an agent to press it") and was told no each time | Claude/agent with live keys |
| 2026-11-05 | MindStudio blog guide used only as inspiration | Its `.claude/routines.json` scheduling is unverified; rule limits contradict each other; no `.env` loading | Following it as written |
| 2026-11-05 | Swing + small trend sleeve; Careful risk set; Telegram; paper week with Robot trading fake money | Ethan's choices | — |

## Implementation Notes

- Run tests: `python -m unittest discover -s tests -v` (set `PYTHONIOENCODING=utf-8` on Windows).
- Dry run locally (needs paper keys in env): `PYTHONIOENCODING=utf-8 python -m robot.main --dry-run` — no orders, no files, no Telegram.
- Plan self-check: `python -m robot.plan notebook/plan/<date>.json <date>`. Mission Control: `python -m robot.dashboard [--markdown]`.
- `robot/paper_orders.py` is the only order code; `tests/test_live_guard.py` fails if live mode can reach it (proven by inserting an import).
- `notebook/settings.yaml` can only tighten the Careful limits (ceilings in `robot/settings.py`). Safety brake reset: raise `breaker_reset` by 1.
- Workflow `robot.yml` commits `notebook/state.json` + `trades.jsonl` even after a failed check, so a crash can't make the next run repeat a trade.
- Subagents can't write files whose name contains "report" (a global write hook) — the controller writes those.

- The source guide (mindstudio.ai/blog/build-ai-trading-agent-claude-code-alpaca) mixes 5%/10%/15% position caps and never calls its `validate_order` — don't copy it.
- `trader-memory-core`'s CLI wrapper expects the upstream repo layout; call its scripts directly (e.g. `thesis_store.py --state-dir <dir> list`).
