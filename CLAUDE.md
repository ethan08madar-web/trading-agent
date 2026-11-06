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

- **Current Phase:** Paper test running. Robot (GitHub Actions, every 15 min) + 4 Claude routines (cloud environment `trading-agent`) are live on a new **$1,000** Alpaca paper account. A manual Plan run on 2026-11-06 passed end to end (red light → no picks). Mission Control is now a broker-style page; Telegram messages are bold-titled cards.
- **Current Goal:** Run the 1-week paper test.
- **Current Priority:** Check 2026-11-06 market hours: (1) the first Robot check after 09:30 ET writes `week_start_equity: 1000` and an `equity_history` point to `state.json` — proves GitHub has the new account's keys; then Ethan deletes the old $100k paper account PA3FRQ58C. (2) The 12:30 ET Adjust run used the setup script (no pip installs in its log) and reached `tradermonty.github.io`. (3) Ask Ethan how the new Telegram cards look on his phone.
- **Current Blockers:**
  - Unproven: GitHub keys belong to the new account; environment setup script; the new Telegram card format on a real phone (HTML parse_mode — tested only with mocks).
  - Open: does Alpaca offer read-only keys for live mode (spec §7.3)?
- **Must fix before `mode: live`** (fine for paper): exit price from Alpaca FILL activities (now last-seen price); cash ignores open buy orders/margin; Mission Control badge says "Paper money" always.
- **Known, parked:** trend-sleeve buy crashes the check if the broker returns price 0 (fails safe, ⚠️ alert); a repeating ❌ "failed" order event is sent every check.
- **Recommended Next Task:** `git pull`, read `notebook/state.json` (week_start_equity, equity_history) and `RemoteTrigger list_runs` → `get_run_log` for the latest routine runs; fix anything they hit; watch for the first paper buy on a green/yellow day.

*Last updated: 2026-11-06*

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
- **Telegram:** live alerts as HTML cards (`robot/telegram.py` `card()`; routines use `python -m robot.telegram "Title" "line" ...`). **Mission Control** Artifact page (broker-style; chart from `state.json` `equity_history`): refreshed on each Claude run (not live every 15 min — a ~$5/mo always-on server is the later upgrade if wanted).

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
- [x] Alpaca paper + Telegram connected; GitHub secrets set (2026-11-05)
- [x] Paper account → $1,000; FMP free key; cloud environment; 4 routines (2026-11-06)
- [x] Build Robot + Claude routines + Mission Control (2026-11-05)
- [ ] 1-week paper test → decide on FMP paid and real money

## Important Decisions

| Date | Decision | Why | Alternatives rejected |
|---|---|---|---|
| 2026-11-05 | New project folder `trading-agent`; `stocktrader` untouched | Ethan: stocktrader (Aug 2026 mock React app plan) is unrelated | Reusing stocktrader |
| 2026-11-05 | "Team of two": Robot (GitHub Actions, 15 min) + Claude (3 cloud runs/day) | Watches 4× more often than hourly Claude, protects Pro allowance for other projects, no PC needed | All-Claude hourly (burns Pro, hourly only); everything on PC (stops when PC off) |
| 2026-11-05 | Claude never presses real-money buy/sell; live Robot has no order code | Safety limit; Ethan asked repeatedly (incl. "tell an agent to press it") and was told no each time | Claude/agent with live keys |
| 2026-11-05 | MindStudio blog guide used only as inspiration | Its `.claude/routines.json` scheduling is unverified; rule limits contradict each other; no `.env` loading | Following it as written |
| 2026-11-05 | Plan Task 0 spike passed: a cloud routine (Sonnet 5.5, Default env, no connectors) pushed to `main` directly (commit 48e43be) and republished an Artifact twice at the same URL | Proves the Claude-routine half of the design works without the markdown fallback | `claude/*` branch + Robot reading it; markdown-only Mission Control |
| 2026-11-06 | One read-only script (`robot/research.py`) checks candidates instead of 3 skills | The skills didn't fit: earnings list skips small companies, data checker reads documents, technical analyst needs chart images and its script is a reversal detector. 1 FMP call for all symbols. | Keeping the skills; per-symbol FMP earnings calls (more of the 250/day); lowering the earnings skill's $2B cutoff (edits third-party code) |
| 2026-11-05 | Swing + small trend sleeve; Careful risk set; Telegram; paper week with Robot trading fake money | Ethan's choices | — |
| 2026-11-06 | New $1,000 paper account instead of keeping $100k | Alpaca has no reset; a new account makes sizing match real money (Ethan chose it knowing keys change) | Keep $100k and add an "act as $1,000" setting (extra code to remove before live; buying power still $100k) |
| 2026-11-06 | Own cloud environment `trading-agent`, keys in its plain Environment variables | Network secrets can't inject Alpaca's custom headers, FMP's query param or Telegram's URL token; keys are paper/free/low-risk; a separate env keeps them out of other projects | Default env (shared with other projects); network secrets (don't fit) |
| 2026-11-06 | Routines run with connectors cleared | The server attaches Gmail/Drive/Calendar by default; trading jobs read untrusted web data and must not reach email | Default connectors |
| 2026-11-06 | Mission Control: broker-style page (big value, scrub chart, lamps), original design; always dark (Ethan asked) — light tokens kept under `data-theme="light"` | Ethan asked for a Robinhood-like look; copying a real brand's look is out, the genre layout is fine | Literal Robinhood copy; old tables |
| 2026-11-06 | Robot sends one Telegram card per check | Several events per check were several texts; one card is easier to read | One text per event |

## Implementation Notes

- Run tests: `python -m unittest discover -s tests -v` (set `PYTHONIOENCODING=utf-8` on Windows).
- Dry run locally (needs paper keys in env): `PYTHONIOENCODING=utf-8 python -m robot.main --dry-run` — no orders, no files, no Telegram.
- Plan self-check: `python -m robot.plan notebook/plan/<date>.json <date>`. Mission Control: `python -m robot.dashboard [--markdown]`.
- Candidate checks for the plan run: `python -m robot.research SYM ...` (needs APCA_* keys; FMP_API_KEY for earnings — without it every candidate is DROPped). It replaced `earnings-calendar` (skips companies under $2B), `data-quality-checker` (checks documents, not prices) and `technical-analyst` (needs chart images) in `routines/plan.md` step 3.
- `robot/paper_orders.py` is the only order code; `tests/test_live_guard.py` fails if live mode can reach it (proven by inserting an import).
- `notebook/settings.yaml` can only tighten the Careful limits (ceilings in `robot/settings.py`). Safety brake reset: raise `breaker_reset` by 1.
- Workflow `robot.yml` commits `notebook/state.json` + `trades.jsonl` even after a failed check, so a crash can't make the next run repeat a trade.
- Routines: Claude can create/run cloud routines itself with the `RemoteTrigger` tool (via the `schedule` skill) — don't send Ethan to the claude.ai UI. Environment `env_01FCejMLG8cjQetvPVdwjFMJ` (Default). A brand-new repo needs the Claude GitHub app to see it (github.com/settings/installations → Claude; it was already "All repositories", the first 403 cleared on retry a minute later).
- Routines (created 2026-11-06, Sonnet 5.5, environment `trading-agent` = `env_01F52Mi5WxZm2JmryHCgFBaD`, connectors cleared so they can't touch Gmail/Drive). Cron is UTC, set for EST — **move each 1 hour earlier when DST starts (2027-03-14)**:
  - Plan `trig_01W3Ga64i76UU82QjtFBBEoS` `0 14 * * 1-5` · Adjust `trig_01WeGYmLKJpi8nkvTcBYK682` `30 17 * * 1-5` · Report `trig_01TqMdLJKymoGujLs2HwRH8Q` `30 21 * * 1-5` · Weekly `trig_018LgFfxKobWoHscJoAbWW7A` `0 15 * * 6`
- Environment `trading-agent`: network Limited + Alpaca/FMP/Telegram/Yahoo + `tradermonty.github.io` (market-breadth CSV) + Artifact domains. Setup script pip-installs requests/pyyaml/numpy/pandas for both `python3` and `python` (the cloud image lacks them; added 2026-11-06, first used by the next run).
- First Plan run (manual, 2026-11-06 11:10 UTC) passed: plan committed (191af77), 📋 Telegram 200, Alpaca prices + FMP earnings worked, Mission Control republished at the same URL (v3). Light red → no picks. Keys are in its **Environment variables** box (Ethan typed them). Network secrets were not usable: they only inject Bearer/Basic/body credentials, and Alpaca uses custom headers, FMP a query param, Telegram a URL path. Never put live Alpaca keys there.
- Paper account switched 2026-11-06 to a new $1,000 account (PA3ILFRGT); old $100k account PA3FRQ58C to be deleted once the first market-hours check shows week_start_equity 1000. `state.json` was reset to `{}` for the switch.
- Mission Control Artifact: https://claude.ai/artifact/ESeSSp8YhF3xtomyhf89Wu (created by the spike; routines update it by passing this `url`).
- GitHub Actions secrets set (2026-11-05): `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`. Keys were rotated after being pasted in chat (Alpaca regenerated twice, Telegram `/revoke`); current values were never shared.
- Subagents can't write files whose name contains "report" (a global write hook) — the controller writes those.

- The source guide (mindstudio.ai/blog/build-ai-trading-agent-claude-code-alpaca) mixes 5%/10%/15% position caps and never calls its `validate_order` — don't copy it.
- `trader-memory-core`'s CLI wrapper expects the upstream repo layout; call its scripts directly (e.g. `thesis_store.py --state-dir <dir> list`).
