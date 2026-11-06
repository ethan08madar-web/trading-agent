# trading-agent — Changelog

Notable changes to **this project**, newest first. One dated block per working session.

- Full narrative lives in `session-logs/`. Exact commits live in `git log`.

---

## 2026-11-06

### Changed
- Plan run checks candidates with new `robot/research.py` (earnings for any company size, bad price data, price levels with a default entry/stop/target) instead of `earnings-calendar`, `data-quality-checker` and `technical-analyst`. 10 new tests (68 total).
- `Broker.daily_bars` returns full daily bars; `daily_closes` now uses it.

## 2026-11-05

### Added
- Design spec + implementation plan (`docs/superpowers/`).
- The Robot (`robot/`): settings with Careful ceilings, safety maths, plan validation, read-only broker, paper-only orders, Telegram, the 15-minute check with crash-safe state, Mission Control generator. 58 tests.
- GitHub Actions: `robot.yml` (every 15 min, weekdays) and `tests.yml`.
- Claude routine prompts: `routines/plan.md`, `adjust.md`, `report.md`, `weekly.md`.
- Routine spike passed: a cloud routine pushed to `main` and republished an Artifact at the same URL.
- Alpaca paper keys + Telegram bot wired via GitHub secrets; first real Robot run succeeded.

### Changed
- `robot.yml` skips quietly until Alpaca keys exist (no failure emails during setup).
- Project created; CLAUDE.md with agreed design (Parts 1–2), decisions, risk rules.
- All 74 skills from tradermonty/claude-trading-skills (MIT, d8e71ce) in `.claude/skills/`, safety-scanned (no order placement code).
- `.gitignore` for `.env`, `state/`.
