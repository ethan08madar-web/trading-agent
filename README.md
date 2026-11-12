# trading-agent

A swing-trading assistant. Claude does the research and writes a daily trade plan; a small
Robot program follows the plan and watches prices. It is running on **paper (fake) money**.

**📊 Mission Control (live account page):** https://claude.ai/artifact/ESeSSp8YhF3xtomyhf89Wu
<br><sub>Private: it opens only for the owner's claude.ai account. It is refreshed on each Claude run, not every 15 minutes.</sub>

> Nothing here is investment advice. The rules below are the owner's own choices.

**Want to run your own copy?** Follow [SETUP.md](SETUP.md).

---

## The big picture: two workers

- **Claude (the "brain")** does the research. It runs 3 times each weekday: 9:00 AM (morning
  plan), 12:30 PM (midday check) and 4:30 PM (daily report), plus a weekly review on Saturdays
  (all US Eastern time). It writes a **plan**: a list of stocks it would like to buy and at what prices.
- **The Robot** is a simple Python program that checks prices **every 15 minutes** while the
  market is open (GitHub Actions). It follows the plan and the safety rules. It never makes
  up its own picks.

They never talk to each other directly. Claude writes the plan into this repo
(`notebook/plan/<date>.json`), and the Robot reads it from there.

---

## Part 1: Research before buying (the 9:00 AM plan)

The full instructions are in [routines/plan.md](routines/plan.md).

### Step 1: Check the weather (the "market light")

Before looking at any single stock, Claude checks how the whole market is doing, for example
how many stocks are going up versus down. It picks a light:

- 🟢 **Green**: most stocks are rising. It can hold up to 4 stocks.
- 🟡 **Yellow**: mixed. It can hold up to 2 stocks, and buys nothing new if things are getting worse.
- 🔴 **Red**: the market is weak. **No new buys today.**

The idea is that most stocks follow the market, so you don't buy when the tide is going out.

### Step 2: Find candidates

If the light isn't red, Claude follows **rulebook B** (Ethan's choice, 2026-11-13): find
market **leaders** (stocks that rose the most over the last 6 and 12 months) that are in an
uptrend and have **dipped back** to just above their 20-day average. It uses "screeners"
(filters that scan many stocks, like CANSLIM for strong, growing companies) to gather up to
12 strong candidates.

### Step 3: Safety-check each candidate ([robot/research.py](robot/research.py))

A small script checks every candidate and says **KEEP** or **DROP**. It drops a stock if:

- **The company reports earnings in the next 3 trading days.** Earnings reports can make a
  stock jump or crash overnight, which is too much of a gamble.
- **The price data looks broken**: missing prices, less than 50 days of history, old data, or
  today's price more than 10% away from yesterday's.
- **It isn't a rulebook-B dip**: under a year of history, not in an uptrend (price above the
  50-day average, which is above the 200-day), below its 20-day average, or more than 3% above it.

For each stock it keeps, it works out three prices:

- **Entry max** ("buy up to"): the highest price it will pay. The default is about 1% above the current price.
- **Stop** (the "emergency exit"): if the price falls this low, sell to limit the loss. The
  default is just under the lowest price of the last 10 days.
- **Target**: where to take some profit. It is set so the possible **gain is at least 2× the
  possible loss**. Risk $1 to try to make $2.

The stop can't be more than 15% below the entry, and Claude may only make the plan *safer*
(a higher stop or a lower "buy up to" price), never riskier.

### Step 4: Choose the best 4

Claude keeps the 4 strongest KEEPs (by 6- and 12-month gain), each with a one-line reason. The plan is then checked by
[robot/plan.py](robot/plan.py). If the plan is broken, it counts as "no plan" and the Robot
only manages the stocks it already holds.

---

## Part 2: When does it buy?

Every 15 minutes, for each stock in the plan, the Robot ([robot/main.py](robot/main.py)) asks:

1. Is the **safety brake** off? (See Part 4.)
2. Is there room? (Under the light's limit: 4, 2 or 0 stocks.)
3. Is the price **between the stop and the "buy up to" price**? If the price is too high,
   wait and check again in 15 minutes.
4. Is the price **above the stock's 20-day average**? If not, skip it: rulebook B buys
   strong stocks that dipped *to* that line, not ones that fell through it. If yes, buy.
5. **How much to buy?** It takes the *smallest* of three limits ([robot/safety.py](robot/safety.py)):
   - If the stop is hit, you lose **no more than 1%** of the account.
   - No single stock is **more than 30%** of the account.
   - It can't spend more cash than there is.

**Example with a $1,000 account:** a stock costs $50 and the stop is $46, so you'd lose $4
per share if it goes wrong.

- 1% of $1,000 = $10 allowed loss → $10 ÷ $4 = 2.5 shares
- 30% limit → $300 ÷ $50 = 6 shares
- It takes the smaller number (2.5) and rounds down to **2 shares** ($100). Worst case if
  the stop hits: about **$8 lost**.

This means a bad trade costs about 1% of the account, not a big chunk.

**Note:** because the default "buy up to" price is only 1% above today's price, on a green day
the Robot usually buys on its first check rather than waiting for a "breakout" (the price
pushing above a recent high). The VCP screener gives a breakout price ("pivot"), and Claude
uses it when it has one, so this mostly affects picks from the other two screeners.

### The "trend sleeve" (SPY)

Separately, on green days when SPY (a fund that tracks the 500 biggest US companies) is above
its 50-day average price, the Robot can hold some SPY (up to 30% of the account). It sells
when SPY closes below that average.

---

## Part 3: When does it sell?

For every stock it owns, the Robot checks these rules in this order:

| Rule | What happens | Why |
|---|---|---|
| 🛑 Price falls to the **stop** | Sell everything | Cut the loss while it's small |
| 📅 **Earnings within 2 days** | Sell everything | Avoid the overnight gamble |
| 📉 Closes **below its 50-day average** (checked at end of day) | Sell everything | The upward trend looks broken (rulebook B, since 2026-11-13; was the 20-day line, which sold winners too early) |
| 🎯 Price reaches the **target** | Sell **half**, and move the stop up to the price paid | Lock in profit; the other half now can't turn into a loss |

Two more things:

- **Stops only move up, never down.** At midday ([routines/adjust.md](routines/adjust.md))
  Claude can raise a stop when the stock has risen, which protects profit. It can never lower
  one to "give it more room."
- At midday Claude can also **cancel** planned buys if the market got worse or a stock broke down.

---

## Part 4: The safety brake

**All new buying stops** if:

- the account is **down 5% in one week**, or
- there were **3 losing trades in a row**.

It stays stopped until the owner turns it back on by raising `breaker_reset` by 1 in
[notebook/settings.yaml](notebook/settings.yaml). These limits are written into the code
([robot/settings.py](robot/settings.py)), so `settings.yaml` can only make them stricter, and
even if Claude made a mistake in the plan, the Robot would refuse to break them.

---

## Real money

Right now it uses **paper (fake) money**, and the Robot places the fake trades itself
([robot/paper_orders.py](robot/paper_orders.py) is the only order code). In live mode the
Robot **has no code to place real orders at all**: it only sends a Telegram message like
"Buy 2 XYZ at up to $50, stop $46", and the owner decides and places the trade in the Alpaca
app. A test ([tests/test_live_guard.py](tests/test_live_guard.py)) fails if live mode can
ever reach the order code.

---

## The scoreboard (time machine)

To know whether these rules actually work, the `backtest/` folder replays them on real past
prices from 2019 to today, with a pretend $1,000 and the Robot's own safety rules. Four
rulebooks compete against simply holding SPY:

- **A.** Today's bot, as a computer would run it alone (no Claude judgment).
- **B.** Momentum leaders (the strongest 10% of stocks over the past year) bought on a small dip.
- **C.** The same leaders bought when they break above their recent high on heavy trading.
- **D.** Just hold SPY while it's above its 200-day average.

Rules may only be tuned on 2019–2023. The years 2024 → today are kept hidden as a final exam.
A rulebook passes if it beats holding SPY for return per worst drop, is no more than 2 points a
year behind it, and made at least 100 trades. Reports are saved in [backtest/results/](backtest/results/).

```bash
python -m backtest.run           # tune years only
python -m backtest.run --final   # also the hidden years
```

**First results (2026-11-06, [full report](backtest/results/2026-11-06-final.md)):** no rulebook
passed. Just holding SPY made the most money in both periods. The most consistent stock-picker
was **B** (profitable in both periods, smaller drops than SPY, but about half SPY's return). The
replay also found that today's bot can buy a stock under its 20-day average and sell it at the
same day's close. **Ethan switched the bot to B on 2026-11-13.** The 2024 → today exam has now been used, so later changes need a fresh one
(more time passing, or paper results).

Free data, no keys: Yahoo daily prices and the list of past S&P 500 members
([fja05680/sp500](https://github.com/fja05680/sp500), MIT). Each report lists what it can't
tell you (daily prices only, no earnings dates, no Claude).

## For developers

- Project notes, decisions and status: [CLAUDE.md](CLAUDE.md). Design: [docs/superpowers/specs/](docs/superpowers/specs/).
- Run tests: `python -m unittest discover -s tests -v` (on Windows set `PYTHONIOENCODING=utf-8`).
- Dry run (needs paper keys in the environment): `python -m robot.main --dry-run` — no orders, no files, no Telegram.
- Keys live in a gitignored `.env`, GitHub Actions secrets and the cloud environment — never in this repo.
