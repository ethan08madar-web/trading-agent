# Scoreboard (research upgrade piece 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A day-by-day replay ("time machine") of the bot's rules on 2019→today that scores 4 rulebooks against buying and holding SPY.

**Architecture:** A new `backtest/` package: `data.py` (free Yahoo bars + past S&P 500 members, cached), `indicators.py` (trailing-only averages/highs/lows), `market.py` (market light + leaders per day), `rulebooks.py` (the 4 contestants), `engine.py` (pretend $1,000 account using `robot/safety.py`), `report.py` + `run.py` (metrics, pass mark, markdown report). The Robot's exit order moves into `safety.exit_reason` so the Robot and the replay share one copy.

**Tech Stack:** Python 3.12 stdlib only (no new dependencies), `unittest`.

**Spec:** `docs/superpowers/specs/2026-11-06-research-upgrade-design.md`

## Global Constraints

- No new dependencies; stdlib only. Tests: `python -m unittest discover -s tests -v` with `PYTHONIOENCODING=utf-8`.
- Rules are reused from `robot/safety.py`; never copied. Careful limits come from `notebook/settings.yaml` via `robot.settings.load_settings`.
- Tune years 2019-01-01 → 2023-12-31. Held-out years 2024-01-01 → today, run only with `--final`.
- Pass mark: yearly return ÷ worst drop beats SPY's, yearly return ≥ SPY's − 2 points, ≥100 trades over tune + held-out.
- Costs: 0.10% slippage per fill. Start: $1,000 per period.
- No future data: every value used on day *i* is computed from bars ≤ *i*.
- `backtest/cache/` is gitignored; reports in `backtest/results/` are committed.
- Data changes from the spec: Yahoo instead of Alpaca (no keys needed); earnings are not modelled (no free history) — said in every report.

---

### Task 1: Shared exit rule

**Files:** Modify `robot/safety.py` (append), `robot/main.py:157-168`; Test `tests/test_safety.py`

**Interfaces:** Produces `safety.exit_reason(m, low, high, close, avg20, sell_earnings=False) -> "stop"|"earnings"|"avg20"|"target"|None`; `m` needs keys `stop`, `target`, `half_sold`.

- [ ] Step 1: failing test in `tests/test_safety.py`:

```python
class ExitTest(unittest.TestCase):
    def test_order(self):
        m = {"stop": 90, "target": 120, "half_sold": False}
        self.assertEqual(safety.exit_reason(m, 89, 125, 100, 110), "stop")  # stop beats everything
        self.assertEqual(safety.exit_reason(m, 95, 125, 100, None, True), "earnings")
        self.assertEqual(safety.exit_reason(m, 95, 125, 100, 110), "avg20")
        self.assertEqual(safety.exit_reason(m, 95, 125, 115, 110), "target")
        self.assertIsNone(safety.exit_reason({**m, "half_sold": True}, 95, 125, 115, 110))
        self.assertIsNone(safety.exit_reason({**m, "stop": None}, 50, 100, 100, None))
```

- [ ] Step 2: run, expect AttributeError.
- [ ] Step 3: implement in `robot/safety.py`:

```python
def exit_reason(m, low, high, close, avg20, sell_earnings=False):
    """Why to sell a swing position now, or None; checked in this order (spec §4).
    The Robot passes its one live price as low/high/close; the backtest passes the day's bar.
    avg20 is None except at the close."""
    if m["stop"] and low <= m["stop"]:
        return "stop"
    if sell_earnings:
        return "earnings"
    if avg20 and close < avg20:
        return "avg20"
    if m["target"] and not m["half_sold"] and high >= m["target"]:
        return "target"
    return None
```

and in `robot/main.py` replace the `if m["stop"] and price <= m["stop"]: … elif m["target"] …` chain with:

```python
        why = safety.exit_reason(m, price, price, price, avg20, sym in plan["sell_earnings"])
        if why == "stop":
            sell(sym, qty, f"stop ${m['stop']:.2f} hit", "🛑", price)
        elif why == "earnings":
            sell(sym, qty, "earnings within 2 days", "📅", price)
        elif why == "avg20":
            sell(sym, qty, "below its 20-day average at the close", "📉", price)
        elif why == "target":
            half = safety.round_qty(qty / 2)
            if half <= 0 or sell(sym, half, f"target ${m['target']:.2f} hit, stop now at entry ${m['entry']:.2f}",
                                 "🎯", price):
                m.update(half_sold=True, stop=m["entry"])
```

- [ ] Step 4: full suite passes (68 existing + 1).
- [ ] Step 5: commit `Move the Robot's exit order into safety.exit_reason`.

### Task 2: Free price data

**Files:** Create `backtest/__init__.py` (empty), `backtest/data.py`; Modify `.gitignore` (add `backtest/cache/`); Test `tests/test_backtest.py`

**Interfaces:** Produces `load_members(text) -> [(date, set)]`, `members_on(rows, day) -> set`, `yahoo_bars(payload) -> [{t,o,h,l,c,v}]`, `members(refresh=False) -> rows`, `bars(sym, refresh=False) -> list` (`[]` if Yahoo has no such symbol).

- [ ] Step 1: failing tests:

```python
class DataTest(unittest.TestCase):
    def test_members_on(self):
        rows = data.load_members('date,tickers\n2017-05-01,"OLD"\n2019-01-02,"A,B"\n2019-03-01,"A,C"\n')
        self.assertEqual(len(rows), 2)  # rows before 2018 dropped
        self.assertEqual(data.members_on(rows, "2019-02-15"), {"A", "B"})
        self.assertEqual(data.members_on(rows, "2019-03-01"), {"A", "C"})
        self.assertEqual(data.members_on(rows, "2018-12-31"), set())

    def test_yahoo_bars_adjusts_and_drops_bad_rows(self):
        p = {"chart": {"result": [{"timestamp": [1546439400, 1546525800],
             "indicators": {"quote": [{"open": [100, None], "high": [110, 1], "low": [90, 1],
                                       "close": [100, 1], "volume": [5, 1]}],
                            "adjclose": [{"adjclose": [50, 1]}]}}]}}
        self.assertEqual(data.yahoo_bars(p), [{"t": "2019-01-02", "o": 50, "h": 55, "l": 45, "c": 50, "v": 5}])
```

- [ ] Step 2: run, expect ImportError.
- [ ] Step 3: implement `backtest/data.py` (code as committed in Task 2's commit; members CSV `fja05680/sp500` "(Updated)" file, MIT; Yahoo `v8/finance/chart`; cache JSON per symbol; 404 cached as `[]`, other errors raise; 0.3 s pause between downloads; `.`→`-` in Yahoo symbols).
- [ ] Step 4: tests pass; live smoke: `python -c "from backtest import data; print(len(data.bars('AAPL')), data.bars('AAPL')[-1])"` prints ~2,200 bars ending this week.
- [ ] Step 5: commit `backtest: free price data (Yahoo bars, past S&P 500 members)`.

### Task 3: Indicators and market light

**Files:** Create `backtest/indicators.py`, `backtest/market.py`; Test `tests/test_backtest.py`

**Interfaces:** Produces `rolling_mean(xs, n)`, `rolling_ext(xs, n, better)`, `series(bars) -> dict` with keys `t o h l c v idx sma20 sma50 sma200 low10 high10 low50 high50 high252 prev_high20 vol50 rs`; `market_light(close, sma50, sma200, breadth, breadth_5d_ago) -> (light, falling)`; `prepare(X, rows, days) -> (members_by_day, leaders, lights)`.

- [ ] Step 1: failing tests — `rolling_mean([1,2,3,4,5],3) == [None,None,2,3,4]`; rolling max/min; **no-lookahead**: for random-walk bars, `series(bars[:k])[key][k-1] == series(bars)[key][k-1]` for every key and several k; light cases: SPY under 200-day → red; breadth 0.6 and SPY over 50-day → green; breadth 0.45 → yellow; falling when breadth dropped > 5 points.
- [ ] Step 2: run, expect ImportError.
- [ ] Step 3: implement (light: red if SPY < 200-day or breadth < 0.35; green if SPY > 50-day and breadth ≥ 0.55; else yellow; leaders = top 10% by `rs = ½·6-month + ½·12-month return`).
- [ ] Step 4: pass. Step 5: commit `backtest: trailing indicators and market light`.

### Task 4: Rulebooks

**Files:** Create `backtest/rulebooks.py`; Test `tests/test_backtest.py`

**Interfaces:** Produces `pick(entry, stop, score, s)`, finders `twin`, `pullback`, `breakout` with signature `(x, i, leader, s) -> {entry_max, stop, target, score} | None`, and `BOOKS` = list of `{"name", "find", "sleeve", "params"}`; sleeve = `{"weight", "entry_avg", "exit_avg", "need_green"}` or None.

- [ ] Step 1: failing tests — `pick` rejects a stop 20% away and sets target = entry + 2×risk; `breakout` fires for a leader closing above its prior 20-day high on 2× volume and not for a non-leader; `twin` fires on a +5% day with rising volume.
- [ ] Step 2–4: implement, pass. Books: A twin (VCP-lite + momentum burst, 30% SPY sleeve over 50-day on green), B pullback leaders (+ sleeve), C breakout leaders (+ sleeve), D trend only (100% SPY over 200-day, no picks).
- [ ] Step 5: commit `backtest: four rulebooks`.

### Task 5: Replay engine

**Files:** Create `backtest/engine.py`; Test `tests/test_backtest.py`

**Interfaces:** Consumes `safety.exit_reason/position_size/max_positions_for/breaker_reason/round_qty/is_loss`. Produces `run(book, X, days, lights, leaders, members_by_day, s, start_cash=1000.0) -> {"equity": [(day, value)], "trades": [{symbol,in,out,entry,exit,pnl_pct,why,sleeve}]}`.

Day order: (1) yesterday's orders fill — skipped if the open is at/below the stop or the low never reaches `entry_max`; fill at min(open, entry_max) + 0.10%; sleeve orders fill at the open. (2) exits via `exit_reason` on the day's bar — stop fills at min(open, stop), target sells half at max(open, target) and moves the stop to entry, 20-day rule at the close; a symbol whose data ended is sold at its last close. (3) value the account; new week → new week-start value; safety brake trips on `breaker_reason` and (assumption, stated in reports) is reset the next Monday. (4) unless paused: tomorrow's orders — sleeve first, then candidates best score first while under the light's cap, sized by `position_size` with cash already promised to earlier orders taken out.

- [ ] Step 1: failing hand-checked test: one stock, finder fires only on day 0 (entry_max 10, stop 9, target 12, green light). Bars: d0 10/10/10/10; d1 open 9.8 low 9.7 → 10 shares at 9.8098; d2 open 11 high 12.5 → 5 sold at 11.988, stop → 9.8098; d3 open 9.5 → 5 sold at 9.4905 "stop". Expect one trade, pnl ≈ +9.47%, final value 1009.29. Second test: d1 opens at 8.9 (below the stop) → no trade, value 1000.
- [ ] Step 2–4: implement, pass.
- [ ] Step 5: commit `backtest: day-by-day replay engine`.

### Task 6: Report, runner, real run, docs

**Files:** Create `backtest/report.py`, `backtest/run.py`, `backtest/results/`; Modify `README.md`, `CLAUDE.md`, `CHANGELOG.md`, spec (data-source note); Test `tests/test_backtest.py`

**Interfaces:** Produces `drawdown(values)`, `metrics(curve, trades)`, `passes(m, spy, total_trades)`, CLI `python -m backtest.run [--final] [--refresh]`.

- [ ] Step 1: failing tests — drawdown of [100,120,90,130] = 25%; `passes` true/false cases incl. <100 trades.
- [ ] Step 2–4: implement; the report also runs `.claude/skills/backtest-expert/scripts/evaluate_backtest.py` per rulebook and quotes its verdict.
- [ ] Step 5: real run — fetch (~10 min, background), `python -m backtest.run`, read the report, sanity-check (SPY benchmark matches SPY's real 2019–2023 return ≈ +100%; trade counts non-zero; missing symbols listed).
- [ ] Step 6: `--final` run once; docs; commit; merge to `main`; push.
