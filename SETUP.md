# Setup — run your own copy

This guide is for someone new (no context needed) who wants to run trading-agent themselves.
Read [README.md](README.md) first for what the bot does. It runs on **paper (fake) money**.
Nothing here is investment advice.

Time: about 1 hour. Cost: free (Claude Pro or higher is needed for the Claude half).

---

## What you are setting up

| Piece | Where it runs | What it needs |
|---|---|---|
| **Robot** (checks prices every 15 min, places paper trades) | GitHub Actions in **your own** repo | Alpaca paper keys, Telegram bot |
| **Claude routines** (writes the daily plan, 4 scheduled runs) | Claude Code cloud, on **your** claude.ai account | Same keys + an FMP key |
| **Notebook** (plan, trades, diary) | The `notebook/` folder in your repo | nothing |

Important: **use your own copy of the repo and your own keys.** If two people's robots run
against the same repo they will fight over `notebook/state.json`.

---

## Step 1 — Your own private copy

1. On GitHub, create a new **private** repo (e.g. `trading-agent`), with no README.
2. On your computer:
   ```bash
   git clone https://github.com/ethan08madar-web/trading-agent.git
   cd trading-agent
   git remote set-url origin https://github.com/<you>/trading-agent.git
   ```
3. Clear the original owner's trading history so you start fresh:
   ```bash
   echo {} > notebook/state.json
   : > notebook/trades.jsonl
   git commit -am "Start my own notebook"
   git push -u origin main
   ```
   (The old `notebook/plan/` and `notebook/diary/` files are fine to keep as examples, or delete them.)

## Step 2 — Accounts and keys (all free)

1. **Alpaca** (broker): sign up at alpaca.markets → switch to **Paper Trading** → set the paper
   balance (the rules are tuned for **$1,000**) → generate API keys. You get a Key ID and a Secret.
2. **Telegram** (alerts to your phone): in Telegram, message `@BotFather` → `/newbot` → copy the
   **bot token**. Send your new bot any message, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id` — that's your **chat id**.
3. **FMP** (earnings dates for the research step): sign up at financialmodelingprep.com → copy the
   free API key (250 calls/day is enough). Without it, every candidate stock gets dropped.

Never paste keys into a chat, an issue, or a committed file. If one leaks, regenerate it.

## Step 3 — Run it on your computer (optional but recommended)

Needs Python 3.12.

```bash
pip install -r requirements.txt
cp .env.example .env        # then fill in your keys in .env (it is gitignored)
python -m unittest discover -s tests -v
```

On Windows, set `PYTHONIOENCODING=utf-8` first. All tests should pass.

Dry run (reads real paper prices, places **no** orders, writes no files, sends no Telegram).
Load the keys from `.env` into your shell first, then:

```bash
python -m robot.main --dry-run
```

## Step 4 — Turn on the Robot (GitHub Actions)

In your repo: **Settings → Secrets and variables → Actions → New repository secret**. Add 4:

- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Then **Actions** tab → enable workflows. To test: Actions → **robot** → Run workflow (leave
"dry_run" ticked). It then runs by itself every 15 minutes on weekdays during market hours.

Also in **Settings → Actions → General → Workflow permissions**, choose **Read and write** so
the Robot can save `notebook/state.json`.

## Step 5 — Turn on the Claude half (routines)

The 4 routines are in [routines/](routines/): `plan.md` (9:00 ET), `adjust.md` (12:30 ET),
`report.md` (4:30 PM ET), `weekly.md` (Saturdays). Easiest way: open this repo in Claude Code and
ask it to "set up the 4 routines from SETUP.md". It needs:

1. The **Claude GitHub app** able to see your repo (github.com/settings/installations → Claude).
2. A **cloud environment** of its own with:
   - Network access: **Limited/Custom**, allowing `paper-api.alpaca.markets`, `data.alpaca.markets`,
     `financialmodelingprep.com`, `api.telegram.org`, Yahoo Finance hosts, `tradermonty.github.io`.
   - **Environment variables** (the plain box, not "network secrets"): `APCA_API_KEY_ID`,
     `APCA_API_SECRET_KEY`, `FMP_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
   - A setup script: `pip install requests pyyaml numpy pandas`.
3. Each routine created with its connectors **cleared** (no Gmail/Drive/Calendar — these jobs
   read web data and must not touch your email).
4. Cron times are in UTC: `0 14 * * 1-5`, `30 17 * * 1-5`, `30 21 * * 1-5`, `0 15 * * 6`
   (that's EST; move each 1 hour earlier when daylight saving starts).

**Mission Control** (the account page) is a claude.ai Artifact. The first routine run creates
your own; then put its URL in your `CLAUDE.md` so later runs update the same page.

## Step 6 — Check it worked

- The first weekday after setup, your Telegram gets a 📋 plan card around 9:00 ET.
- A new `notebook/plan/<date>.json` appears in your repo.
- During market hours, `robot: check …` commits appear every 15 minutes.
- If a check fails, Telegram gets a ⚠️ message with a link to the run.

## Rules you should know before changing anything

- Risk limits live in code ([robot/settings.py](robot/settings.py)). `notebook/settings.yaml` can
  only make them **stricter**.
- Safety brake (−5% in a week or 3 losses in a row) stops new buys until you raise
  `breaker_reset` by 1 in `notebook/settings.yaml`.
- Live (real money) mode has **no order code**: it only sends Telegram alerts and you place the
  trade yourself. Several things in [CLAUDE.md](CLAUDE.md) "Must fix before `mode: live`" are not
  done yet — stay on paper.
- Backtest: `python -m backtest.run` (see README "The scoreboard").
