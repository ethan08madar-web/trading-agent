# trading-agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Robot (a Python rules program on GitHub Actions), the Claude routine prompts, and the Mission Control page generator, so a 1-week paper-money test can run.

**Architecture:** Claude (a cloud routine, 3 runs a weekday) writes `notebook/plan/<date>.json`. The Robot runs every 15 minutes on GitHub Actions. It reads the plan, enforces every safety rule in `robot/safety.py`, places **paper** orders through `robot/paper_orders.py` (the only file that can place orders), and writes `notebook/state.json` and `notebook/trades.jsonl`. In live mode the Robot only sends Telegram alerts.

**Tech Stack:** Python 3.12 (stdlib + PyYAML 6), `unittest`, Alpaca REST API (paper; IEX data feed), Telegram Bot API, GitHub Actions, Claude Code cloud routines.

**Spec:** `docs/superpowers/specs/2026-11-05-trading-agent-design.md`

## Global Constraints

- Claude, and any agent Claude starts, never places real-money trades. Live mode = Telegram alerts only. No order code is reachable in live mode.
- `robot/paper_orders.py` is the only file that may contain `v2/orders`. Its base URL is hardcoded: `https://paper-api.alpaca.markets`.
- Careful limits (ceilings enforced in `robot/settings.py`; settings may only make them stricter):
  - risk per trade ≤ 1% of equity
  - one position ≤ 30% of equity
  - at most 4 positions
  - pause new buys after −5% in a week, or after 3 losses in a row
- Market light: green → up to 4 positions; yellow → up to 2, and 0 if falling; red → 0.
- Python 3.12, stdlib + `pyyaml>=6` only. Tests use `unittest`: `python -m unittest discover -s tests -v`.
- Never print or log API keys or tokens. Keys go in GitHub Actions secrets and Claude cloud environment secrets, typed in by Ethan. Never in chat, never in the repo.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Work on a `feat/robot` branch; merge to `main` with `--no-ff` when all tasks pass.
- Windows dev machine: set `PYTHONIOENCODING=utf-8` when running the Robot locally (emoji output).
- Steps marked **[Ethan]** need Ethan. Give him one step per message, with the exact button or text, and check the result before the next step.

## File map

| File | Responsibility |
|---|---|
| `requirements.txt` | `pyyaml>=6` |
| `notebook/settings.yaml` | Ethan's rules (mode, limits, breaker reset) |
| `notebook/state.json` | Robot memory (created by the first run) |
| `notebook/trades.jsonl` | Robot event log (append only) |
| `notebook/plan/<date>.json` | Claude's daily plan |
| `notebook/diary/*.md` | Claude's reports |
| `robot/settings.py` | load and check settings |
| `robot/safety.py` | pure maths: sizing, caps, breaker, averages |
| `robot/plan.py` | validate a plan; CLI for Claude to self-check |
| `robot/broker.py` | read-only Alpaca calls |
| `robot/paper_orders.py` | the ONLY order-placing code (paper URL hardcoded) |
| `robot/telegram.py` | send a message; never raises |
| `robot/main.py` | one check (`run_check`) + CLI |
| `robot/dashboard.py` | Mission Control HTML from the notebook |
| `routines/*.md` | prompts for the Claude cloud routines |
| `.github/workflows/robot.yml`, `tests.yml` | schedule and CI |
| `tests/test_*.py` | one test file per module |

---

### Task 0: Spike — can a cloud routine push to `main` and republish an Artifact? [Ethan + Claude]

Spec §3.5 and setup step 5. This runs **before Task 10**. Tasks 1–9 don't depend on it and can go ahead in parallel.

**Files:**
- Create (temporary, deleted at the end): `notebook/spike.txt`

- [ ] **Step 1 [Ethan]:** In claude.ai/code, create a routine on repo `ethan08madar-web/trading-agent`, run once (manual trigger), with this prompt:

  ```
  Write the current UTC time to notebook/spike.txt, commit it with message "spike: routine push test", and push to main.
  Then publish a one-line HTML Artifact titled "Mission Control spike" containing the same time, and reply with its URL.
  ```

- [ ] **Step 2:** Check the results:
  - `git fetch && git log origin/main -1 -- notebook/spike.txt` shows the commit → pushing to main works.
  - The routine's transcript shows an Artifact URL → publishing works. Ask Ethan to open the URL and confirm.
  - Run it a second time → does it update the **same** URL? That's needed for Mission Control.

- [ ] **Step 3:** Record the answers in `CLAUDE.md` (Current Blockers and Important Decisions).
  - If the push only reached a `claude/…` branch: find the routine or environment setting that allows pushing to `main` and have Ethan turn it on. If no such setting exists, **stop and redesign with Ethan**. The Robot only reads `main`.
  - If the Artifact can't be published or updated: use the fallback, a committed `notebook/MISSION_CONTROL.md` (Task 9 adds `--markdown`).

- [ ] **Step 4:** Delete `notebook/spike.txt`. Commit: `chore: record routine spike result`.

---

### Task 1: Scaffold + settings loader

**Files:**
- Create: `requirements.txt`, `robot/__init__.py` (empty), `notebook/settings.yaml`, `notebook/trades.jsonl` (empty), `notebook/plan/.gitkeep`, `notebook/diary/.gitkeep`, `robot/settings.py`
- Test: `tests/__init__.py` (empty), `tests/test_settings.py`

**Interfaces:**
- Produces: `load_settings(path: str) -> dict` with keys
  - `mode` (`"paper"|"live"`)
  - `risk_per_trade`, `max_position`, `max_stop_distance`, `week_loss_limit` (float)
  - `max_positions`, `loss_streak_limit`, `breaker_reset` (int)
  - `sleeve_symbol` (str)

  Raises `ValueError` on anything invalid.

- [ ] **Step 1: Create branch and scaffold**

```bash
cd C:/Users/ethan/Claude/trading-agent && git checkout -b feat/robot
mkdir -p robot tests notebook/plan notebook/diary
touch robot/__init__.py tests/__init__.py notebook/trades.jsonl notebook/plan/.gitkeep notebook/diary/.gitkeep
printf 'pyyaml>=6\n' > requirements.txt
```

`notebook/settings.yaml`:

```yaml
# Ethan's rules. The Robot refuses limits looser than the "Careful" set (robot/settings.py).
mode: paper              # paper = Robot places fake trades. live = Telegram alerts only; Ethan trades.
risk_per_trade: 0.01     # max loss if the stop hits, as a share of the account (max 0.01)
max_position: 0.30       # max share of the account in one position (max 0.30)
max_positions: 4         # max open positions, trend sleeve included (max 4)
max_stop_distance: 0.15  # reject picks whose stop is more than 15% below entry
week_loss_limit: 0.05    # pause new buys after this loss in a week (max 0.05)
loss_streak_limit: 3     # pause new buys after this many losses in a row (max 3)
sleeve_symbol: SPY       # trend sleeve
breaker_reset: 0         # safety brake on? raise this number by 1 to allow buying again
```

- [ ] **Step 2: Write the failing test** — `tests/test_settings.py`

```python
import os
import tempfile
import unittest

from robot.settings import load_settings

GOOD = """mode: paper
risk_per_trade: 0.01
max_position: 0.30
max_positions: 4
max_stop_distance: 0.15
week_loss_limit: 0.05
loss_streak_limit: 3
sleeve_symbol: SPY
breaker_reset: 0
"""


def write(text):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class SettingsTest(unittest.TestCase):
    def test_good_file_loads(self):
        s = load_settings(write(GOOD))
        self.assertEqual(s["mode"], "paper")
        self.assertEqual(s["max_positions"], 4)
        self.assertIsInstance(s["max_position"], float)

    def test_repo_settings_file_is_valid(self):
        self.assertEqual(load_settings("notebook/settings.yaml")["mode"], "paper")

    def test_bad_values_rejected(self):
        for old, new in [
            ("mode: paper", "mode: real"),
            ("risk_per_trade: 0.01", "risk_per_trade: 0.02"),   # looser than Careful
            ("max_positions: 4", "max_positions: 5"),
            ("week_loss_limit: 0.05", "week_loss_limit: 0.10"),
            ("loss_streak_limit: 3", "loss_streak_limit: true"),
            ("sleeve_symbol: SPY\n", ""),
        ]:
            with self.subTest(new=new):
                with self.assertRaises(ValueError):
                    load_settings(write(GOOD.replace(old, new)))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run it and see it fail**

Run: `python -m unittest tests.test_settings -v`
Expected: `ModuleNotFoundError: No module named 'robot.settings'`

- [ ] **Step 4: Implement** — `robot/settings.py`

```python
"""Load and check notebook/settings.yaml (spec §4).

The ceilings are Ethan's "Careful" limits: settings can make them stricter, never looser.
Loosening one is a code change on purpose, not a typo in a YAML file."""
import yaml

FLOATS = {"risk_per_trade": 0.01, "max_position": 0.30,
          "max_stop_distance": 0.25, "week_loss_limit": 0.05}
INTS = {"max_positions": (1, 4), "loss_streak_limit": (1, 3), "breaker_reset": (0, 10**6)}


def load_settings(path):
    with open(path, encoding="utf-8") as f:
        s = yaml.safe_load(f) or {}
    if s.get("mode") not in ("paper", "live"):
        raise ValueError("settings: mode must be paper or live")
    if not isinstance(s.get("sleeve_symbol"), str):
        raise ValueError("settings: sleeve_symbol must be a ticker")
    for k, ceiling in FLOATS.items():
        v = s.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v <= ceiling:
            raise ValueError(f"settings: {k} must be a number above 0 and at most {ceiling}")
        s[k] = float(v)
    for k, (lo, hi) in INTS.items():
        v = s.get(k)
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ValueError(f"settings: {k} must be a whole number from {lo} to {hi}")
    return s
```

- [ ] **Step 5: Run it and see it pass**

Run: `python -m unittest tests.test_settings -v` → 3 tests OK.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt robot tests notebook
git commit -m "feat: robot scaffold and settings loader with Careful ceilings"
```

---

### Task 2: Safety maths

**Files:**
- Create: `robot/safety.py`
- Test: `tests/test_safety.py`

**Interfaces:**
- Consumes: the settings dict from Task 1.
- Produces:
  - `floor2(x: float) -> float`
  - `round_qty(qty: float) -> float` — whole shares if ≥ 1, else fractional floored to 0.01
  - `position_size(equity, cash, entry, stop, s) -> float` — returns 0 for "don't buy"
  - `max_positions_for(light: str, falling: bool, s) -> int`
  - `breaker_reason(equity, week_start_equity, loss_streak, s) -> str | None`
  - `is_loss(entry, exit_price) -> bool`
  - `sma(values: list[float], n: int) -> float | None`

- [ ] **Step 1: Write the failing test** — `tests/test_safety.py`

```python
import unittest

from robot import safety

S = {"risk_per_trade": 0.01, "max_position": 0.30, "max_positions": 4,
     "max_stop_distance": 0.15, "week_loss_limit": 0.05, "loss_streak_limit": 3}


class SizeTest(unittest.TestCase):
    def test_cash_is_the_tightest_cap(self):
        # risk 10/2.5 = 4 shares, 30% cap 6, cash 1000/50 = 20 -> 4
        self.assertEqual(safety.position_size(1000, 1000, 50, 47.5, S), 4)

    def test_30_percent_cap_wins(self):
        # risk 10/7.5 = 1.33, cap 300/231.5 = 1.29 -> whole share 1
        self.assertEqual(safety.position_size(1000, 1000, 231.5, 224, S), 1)

    def test_fractional_below_one_share(self):
        # risk 10/10 = 1, cap 300/500 = 0.6 -> 0.6
        self.assertEqual(safety.position_size(1000, 1000, 500, 490, S), 0.6)

    def test_rejects(self):
        self.assertEqual(safety.position_size(1000, 1000, 100, 100, S), 0)  # stop not below entry
        self.assertEqual(safety.position_size(1000, 1000, 100, 80, S), 0)   # stop 20% away > 15%
        self.assertEqual(safety.position_size(1000, 0, 50, 47.5, S), 0)     # no cash

    def test_floor2_float_safe(self):
        self.assertEqual(safety.floor2(0.29), 0.29)
        self.assertEqual(safety.round_qty(0.296), 0.29)


class RulesTest(unittest.TestCase):
    def test_light_caps(self):
        self.assertEqual(safety.max_positions_for("green", False, S), 4)
        self.assertEqual(safety.max_positions_for("yellow", False, S), 2)
        self.assertEqual(safety.max_positions_for("yellow", True, S), 0)
        self.assertEqual(safety.max_positions_for("red", False, S), 0)

    def test_breaker(self):
        self.assertIsNone(safety.breaker_reason(1000, 1000, 0, S))
        self.assertIn("this week", safety.breaker_reason(1000, 1100, 0, S))   # -9.1%
        self.assertIsNone(safety.breaker_reason(1000, 1050, 0, S))           # -4.8%
        self.assertIn("in a row", safety.breaker_reason(1000, 1000, 3, S))

    def test_is_loss_and_sma(self):
        self.assertTrue(safety.is_loss(50, 47))
        self.assertFalse(safety.is_loss(50, 49.9))   # stop at entry, small slip: not a loss
        self.assertEqual(safety.sma([1, 2, 3, 4], 2), 3.5)
        self.assertIsNone(safety.sma([1], 2))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and see it fail**

Run: `python -m unittest tests.test_safety -v` → `ImportError: cannot import name 'safety'`

- [ ] **Step 3: Implement** — `robot/safety.py`

```python
"""Pure safety maths (spec §4). No network, no files: everything here is unit-tested."""
import math


def floor2(x):
    return math.floor(round(x * 100, 6)) / 100


def round_qty(qty):
    """Whole shares when >= 1 (so a broker stop order can be placed), else 0.01 fractions."""
    return math.floor(qty) if qty >= 1 else floor2(qty)


def position_size(equity, cash, entry, stop, s):
    """Shares to buy: lose at most risk_per_trade if the stop hits, at most max_position
    of the account, and no more than the cash. 0 means don't buy."""
    if entry <= 0 or stop <= 0 or stop >= entry or stop < entry * (1 - s["max_stop_distance"]):
        return 0
    qty = min(s["risk_per_trade"] * equity / (entry - stop),
              s["max_position"] * equity / entry,
              max(cash, 0) / entry)
    return round_qty(qty)


def max_positions_for(light, falling, s):
    if light == "green":
        return s["max_positions"]
    if light == "yellow" and not falling:
        return min(2, s["max_positions"])
    return 0


def breaker_reason(equity, week_start_equity, loss_streak, s):
    if week_start_equity:
        change = equity / week_start_equity - 1
        if change <= -s["week_loss_limit"]:
            return f"account down {abs(change):.1%} this week"
    if loss_streak >= s["loss_streak_limit"]:
        return f"{loss_streak} losing trades in a row"
    return None


def is_loss(entry, exit_price):
    return exit_price < entry * 0.995  # stop moved to entry exits near 0: not a loss


def sma(values, n):
    return sum(values[-n:]) / n if len(values) >= n else None
```

- [ ] **Step 4: Run it and see it pass** — `python -m unittest tests.test_safety -v` → 7 OK.

- [ ] **Step 5: Prove the test can fail.** `cp robot/safety.py robot/safety.py.bak`, change `0.995` to `1.0`, run → `test_is_loss_and_sma` FAILS. Then `mv robot/safety.py.bak robot/safety.py` and run again → OK.

- [ ] **Step 6: Commit** — `git add robot/safety.py tests/test_safety.py && git commit -m "feat: safety maths (sizing, light caps, breaker)"`

---

### Task 3: Plan validation

**Files:**
- Create: `robot/plan.py`
- Test: `tests/test_plan.py`

**Interfaces:**
- Produces:
  - `validate_plan(p, today: str) -> list[str]` — the problems; empty means valid.
  - `load_plan(path: str, today: str) -> tuple[dict | None, list[str]]` — a valid plan with defaults filled in:
    - `light_falling=False`, `picks=[]`, `cancel=[]`, `sell_earnings=[]`, `stops={}`, `trend_sleeve={"hold_spy": False}`
  - CLI: `python -m robot.plan <file> <YYYY-MM-DD>` prints `OK` (exit 0) or the problems (exit 1).

- [ ] **Step 1: Write the failing test** — `tests/test_plan.py`

```python
import json
import os
import subprocess
import sys
import tempfile
import unittest

from robot.plan import load_plan, validate_plan

TODAY = "2026-11-09"
GOOD = {"date": TODAY, "version": 1, "market_light": "green",
        "picks": [{"symbol": "AAPL", "entry_max": 231.5, "stop": 224.0, "target": 246.0, "reason": "x"}]}


def write(obj):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))
    return path


class PlanTest(unittest.TestCase):
    def test_good_plan_gets_defaults(self):
        plan, errs = load_plan(write(GOOD), TODAY)
        self.assertEqual(errs, [])
        self.assertEqual(plan["stops"], {})
        self.assertEqual(plan["trend_sleeve"], {"hold_spy": False})
        self.assertFalse(plan["light_falling"])

    def test_missing_file_and_bad_json(self):
        self.assertIsNone(load_plan("no/such/file.json", TODAY)[0])
        self.assertIsNone(load_plan(write("{not json"), TODAY)[0])

    def test_problems(self):
        cases = {
            "old date": {**GOOD, "date": "2026-11-06"},
            "bad light": {**GOOD, "market_light": "blue"},
            "stop above entry": {**GOOD, "picks": [{**GOOD["picks"][0], "stop": 240.0}]},
            "bad symbol": {**GOOD, "picks": [{**GOOD["picks"][0], "symbol": "aapl;rm"}]},
            "bool price": {**GOOD, "picks": [{**GOOD["picks"][0], "target": True}]},
            "bad stops": {**GOOD, "stops": {"AAPL": "high"}},
            "bad sleeve": {**GOOD, "trend_sleeve": {"hold_spy": "yes"}},
        }
        for name, p in cases.items():
            with self.subTest(name):
                self.assertNotEqual(validate_plan(p, TODAY), [])

    def test_cli(self):
        ok = subprocess.run([sys.executable, "-m", "robot.plan", write(GOOD), TODAY], capture_output=True, text=True)
        bad = subprocess.run([sys.executable, "-m", "robot.plan", write({}), TODAY], capture_output=True, text=True)
        self.assertEqual((ok.returncode, ok.stdout.strip()), (0, "OK"))
        self.assertEqual(bad.returncode, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and see it fail** — `python -m unittest tests.test_plan -v` → `ModuleNotFoundError`

- [ ] **Step 3: Implement** — `robot/plan.py`

```python
"""Validate Claude's daily plan (spec §3.2). A bad plan is treated as no plan.
Claude self-checks with: python -m robot.plan notebook/plan/<date>.json <date>"""
import json
import re
import sys

SYMBOL = re.compile(r"^[A-Z][A-Z.]{0,9}$")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def _symbols(v):
    return isinstance(v, list) and all(isinstance(x, str) and SYMBOL.match(x) for x in v)


def validate_plan(p, today):
    if not isinstance(p, dict):
        return ["plan is not a JSON object"]
    errs = []
    if p.get("date") != today:
        errs.append(f"date {p.get('date')!r} is not today ({today})")
    if p.get("market_light") not in ("green", "yellow", "red"):
        errs.append("market_light must be green, yellow or red")
    if not isinstance(p.get("light_falling", False), bool):
        errs.append("light_falling must be true or false")
    picks = p.get("picks", [])
    if not isinstance(picks, list):
        errs.append("picks must be a list")
        picks = []
    for i, k in enumerate(picks):
        if not isinstance(k, dict) or not isinstance(k.get("symbol"), str) or not SYMBOL.match(k["symbol"]):
            errs.append(f"pick {i}: bad symbol")
        elif not all(_num(k.get(f)) for f in ("entry_max", "stop", "target")):
            errs.append(f"pick {i} {k['symbol']}: entry_max, stop, target must be positive numbers")
        elif not k["stop"] < k["entry_max"] < k["target"]:
            errs.append(f"pick {i} {k['symbol']}: need stop < entry_max < target")
    for key in ("cancel", "sell_earnings"):
        if not _symbols(p.get(key, [])):
            errs.append(f"{key} must be a list of symbols")
    stops = p.get("stops", {})
    if not (isinstance(stops, dict) and _symbols(list(stops)) and all(_num(v) for v in stops.values())):
        errs.append("stops must map symbol -> price")
    ts = p.get("trend_sleeve", {"hold_spy": False})
    if not (isinstance(ts, dict) and isinstance(ts.get("hold_spy"), bool)):
        errs.append("trend_sleeve.hold_spy must be true or false")
    return errs


def load_plan(path, today):
    try:
        with open(path, encoding="utf-8") as f:
            p = json.load(f)
    except (OSError, ValueError) as e:
        return None, [f"cannot read plan: {e}"]
    errs = validate_plan(p, today)
    if errs:
        return None, errs
    for key, default in (("light_falling", False), ("picks", []), ("cancel", []),
                         ("sell_earnings", []), ("stops", {}), ("trend_sleeve", {"hold_spy": False})):
        p.setdefault(key, default)
    return p, []


if __name__ == "__main__":
    plan, problems = load_plan(sys.argv[1], sys.argv[2])
    print("OK" if plan else "\n".join(problems))
    sys.exit(0 if plan else 1)
```

- [ ] **Step 4: Run it and see it pass** — `python -m unittest tests.test_plan -v` → 4 OK.

- [ ] **Step 5: Commit** — `git add robot/plan.py tests/test_plan.py && git commit -m "feat: plan validation + self-check CLI"`

---

### Task 4: Broker (read-only), paper orders, Telegram

**Files:**
- Create: `robot/broker.py`, `robot/paper_orders.py`, `robot/telegram.py`
- Test: `tests/test_io.py`

**Interfaces:**
- Produces:
  - `Broker(mode, key, secret, get=http_get)` with:
    - `.clock() -> dict` (`is_open`, `timestamp`, `next_close`)
    - `.account() -> dict` (`equity`, `cash` as strings)
    - `.positions() -> list[dict]` (`symbol`, `qty`, `avg_entry_price` as strings)
    - `.latest_price(sym) -> float`
    - `.daily_closes(sym, n, before: "YYYY-MM-DD") -> list[float]` — completed days before `before`, oldest first, at most `n`
  - `PaperOrders(key, secret, send=http_send)` with:
    - `.open_orders() -> list[dict]` (`id`, `symbol`, `side`, `type`, `stop_price`)
    - `.buy_limit(sym, qty, limit)`, `.sell_market(sym, qty)`, `.place_stop(sym, qty, stop)`, `.cancel_for(sym)`
  - `PAPER_URL` constant
  - `telegram.send(token, chat_id, text) -> bool` — never raises, never prints the token.

- [ ] **Step 1: Write the failing test** — `tests/test_io.py`

```python
import unittest
from unittest import mock

from robot import paper_orders, telegram
from robot.broker import Broker


class BrokerTest(unittest.TestCase):
    def test_urls_by_mode_and_parsing(self):
        seen = []

        def get(url, headers):
            seen.append(url)
            if "/trades/latest" in url:
                return {"trade": {"p": 101.5}}
            if "/bars" in url:
                return {"bars": [{"t": "2026-11-05T05:00:00Z", "c": 1}, {"t": "2026-11-06T05:00:00Z", "c": 2},
                                 {"t": "2026-11-09T05:00:00Z", "c": 99}]}  # today's partial bar
            return {}

        b = Broker("paper", "k", "s", get=get)
        b.clock()
        self.assertTrue(seen[-1].startswith("https://paper-api.alpaca.markets/v2/clock"))
        Broker("live", "k", "s", get=get).account()
        self.assertTrue(seen[-1].startswith("https://api.alpaca.markets/v2/account"))
        self.assertEqual(b.latest_price("AAPL"), 101.5)
        self.assertEqual(b.daily_closes("AAPL", 5, "2026-11-09"), [1, 2])

    def test_bad_mode(self):
        with self.assertRaises(KeyError):
            Broker("real", "k", "s")


class PaperOrdersTest(unittest.TestCase):
    def test_paper_url_and_bodies(self):
        self.assertEqual(paper_orders.PAPER_URL, "https://paper-api.alpaca.markets")
        calls = []

        def send(method, url, headers, body=None):
            calls.append((method, url, body))
            if method == "GET":
                return [{"id": "1", "symbol": "AAPL"}, {"id": "2", "symbol": "MSFT"}]

        o = paper_orders.PaperOrders("k", "s", send=send)
        o.buy_limit("AAPL", 1, 231.5)
        self.assertEqual(calls[-1][2], {"symbol": "AAPL", "qty": "1", "side": "buy", "type": "limit",
                                        "limit_price": "231.50", "time_in_force": "day"})
        o.place_stop("AAPL", 2, 224)
        self.assertEqual(calls[-1][2]["time_in_force"], "gtc")
        o.cancel_for("AAPL")
        self.assertEqual(calls[-1][:2], ("DELETE", "https://paper-api.alpaca.markets/v2/orders/1"))
        self.assertTrue(all(c[1].startswith(paper_orders.PAPER_URL) for c in calls))


class TelegramTest(unittest.TestCase):
    def test_never_raises(self):
        self.assertFalse(telegram.send("", "", "hi"))
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertFalse(telegram.send("t", "c", "hi"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and see it fail** — `python -m unittest tests.test_io -v` → `ImportError`

- [ ] **Step 3: Implement** — `robot/broker.py`

```python
"""Read-only Alpaca access (spec §3.3). Placing orders lives ONLY in paper_orders.py."""
import json
import urllib.request
from datetime import date, timedelta

TRADING_URL = {"paper": "https://paper-api.alpaca.markets", "live": "https://api.alpaca.markets"}
DATA_URL = "https://data.alpaca.markets"


def http_get(url, headers):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return json.load(r)


class Broker:
    def __init__(self, mode, key, secret, get=http_get):
        self.base = TRADING_URL[mode]
        self.h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.get = get

    def clock(self):
        return self.get(self.base + "/v2/clock", self.h)

    def account(self):
        return self.get(self.base + "/v2/account", self.h)

    def positions(self):
        return self.get(self.base + "/v2/positions", self.h)

    def latest_price(self, sym):
        return float(self.get(f"{DATA_URL}/v2/stocks/{sym}/trades/latest?feed=iex", self.h)["trade"]["p"])

    def daily_closes(self, sym, n, before):
        start = (date.fromisoformat(before) - timedelta(days=n * 2 + 10)).isoformat()
        d = self.get(f"{DATA_URL}/v2/stocks/{sym}/bars?timeframe=1Day&start={start}"
                     f"&limit=1000&adjustment=all&feed=iex", self.h)
        return [b["c"] for b in (d.get("bars") or []) if b["t"][:10] < before][-n:]
```

`robot/paper_orders.py`:

```python
"""The ONLY code that can place orders (spec §3.3). Paper account only: the URL is
hardcoded here on purpose and is never a setting. main.py imports this file only when
mode == paper; tests/test_live_guard.py fails if live mode can reach it."""
import json
import urllib.request

PAPER_URL = "https://paper-api.alpaca.markets"


def http_send(method, url, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


class PaperOrders:
    def __init__(self, key, secret, send=http_send):
        self.h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.send = send

    def _order(self, body):
        return self.send("POST", PAPER_URL + "/v2/orders", self.h, body)

    def open_orders(self):
        return self.send("GET", PAPER_URL + "/v2/orders?status=open&limit=500", self.h)

    def buy_limit(self, sym, qty, limit):
        return self._order({"symbol": sym, "qty": str(qty), "side": "buy", "type": "limit",
                            "limit_price": f"{limit:.2f}", "time_in_force": "day"})

    def sell_market(self, sym, qty):
        return self._order({"symbol": sym, "qty": str(qty), "side": "sell", "type": "market",
                            "time_in_force": "day"})

    def place_stop(self, sym, qty, stop):
        """Whole shares only: Alpaca doesn't accept stop orders for fractional shares."""
        return self._order({"symbol": sym, "qty": str(qty), "side": "sell", "type": "stop",
                            "stop_price": f"{stop:.2f}", "time_in_force": "gtc"})

    def cancel_for(self, sym):
        for o in self.open_orders():
            if o["symbol"] == sym:
                self.send("DELETE", f"{PAPER_URL}/v2/orders/{o['id']}", self.h)
```

`robot/telegram.py`:

```python
"""Telegram alerts. A failed send is logged and ignored: the notebook is the record (spec §5)."""
import urllib.parse
import urllib.request


def send(token, chat_id, text):
    if not token or not chat_id:
        print("telegram not configured:", text)
        return False
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=15)
        return True
    except Exception as e:  # never crash the Robot over an alert
        print("telegram failed:", type(e).__name__, "|", text)
        return False
```

- [ ] **Step 4: Run it and see it pass** — `python -m unittest tests.test_io -v` → 4 OK.

- [ ] **Step 5: Commit** — `git add robot/broker.py robot/paper_orders.py robot/telegram.py tests/test_io.py && git commit -m "feat: read-only broker, paper-only orders, telegram"`

---

### Task 5: One Robot check — exits and bookkeeping

**Files:**
- Create: `robot/main.py` (the `run_check` exits half; Task 6 adds entries and the CLI)
- Test: `tests/test_main.py`

**Interfaces:**
- Consumes:
  - `safety.*` (Task 2)
  - `Broker` / `PaperOrders` method shapes (Task 4)
  - the plan dict with defaults (Task 3)
- Produces:
  - `parse_ts(s) -> datetime`
  - `new_state() -> dict`
  - `run_check(settings, clock, plan, plan_errors, state, broker, orders) -> list[dict]` — events `{type, symbol, text}`; `orders` is `None` in live mode; mutates `state`.

State keys:
- `last_check`, `date`, `week`, `week_start_equity`
- `loss_streak`, `paused`, `pause_reason`, `breaker_reset_seen`
- `positions` (`{sym: {entry, stop, target, half_sold, sleeve}}`)
- `pending` (`{sym: {stop, target} | {sleeve: true}}`)
- `bought_today`, `alerted` (`{key: date}`), `last_prices`

- [ ] **Step 1: Write the failing test** — `tests/test_main.py`

```python
import unittest

from robot.main import new_state, run_check

S = {"mode": "paper", "risk_per_trade": 0.01, "max_position": 0.30, "max_positions": 4,
     "max_stop_distance": 0.15, "week_loss_limit": 0.05, "loss_streak_limit": 3,
     "sleeve_symbol": "SPY", "breaker_reset": 0}
LIVE = {**S, "mode": "live"}
OPEN = {"is_open": True, "timestamp": "2026-11-09T10:00:00.123456789-05:00",
        "next_close": "2026-11-09T16:00:00-05:00"}
LATE = {**OPEN, "timestamp": "2026-11-09T15:50:00-05:00"}
PICK = {"symbol": "ABC", "entry_max": 50.0, "stop": 47.5, "target": 56.0, "reason": "x"}


def plan(**kw):
    p = {"date": "2026-11-09", "market_light": "green", "light_falling": False, "picks": [],
         "cancel": [], "sell_earnings": [], "stops": {}, "trend_sleeve": {"hold_spy": False}}
    p.update(kw)
    return p


def holding(sym="ABC", qty="4", entry="50"):
    return {"symbol": sym, "qty": qty, "avg_entry_price": entry}


def meta(**kw):
    m = {"entry": 50.0, "stop": 47.5, "target": 56.0, "half_sold": False, "sleeve": False}
    m.update(kw)
    return m


class FakeBroker:
    def __init__(self, prices=None, positions=None, equity=1000.0, cash=1000.0, closes=None):
        self.prices, self.pos = prices or {}, positions or []
        self.equity, self.cash, self.closes = equity, cash, closes or {}

    def account(self):
        return {"equity": str(self.equity), "cash": str(self.cash)}

    def positions(self):
        return self.pos

    def latest_price(self, sym):
        return self.prices[sym]

    def daily_closes(self, sym, n, before):
        return self.closes.get(sym, [])[-n:]


class FakeOrders:
    def __init__(self, open_orders=None):
        self.calls, self.open = [], open_orders or []

    def open_orders(self):
        return self.open

    def buy_limit(self, s, q, l):
        self.calls.append(("buy", s, q, l))

    def sell_market(self, s, q):
        self.calls.append(("sell", s, q))

    def place_stop(self, s, q, p):
        self.calls.append(("stop", s, q, p))

    def cancel_for(self, s):
        self.calls.append(("cancel", s))


def state_with(**kw):
    st = new_state()
    st.update(date="2026-11-09", week="2026-W46", week_start_equity=1000.0)
    st.update(kw)
    return st


class ExitTest(unittest.TestCase):
    def test_stop_hit_cancels_then_sells(self):
        o = FakeOrders()
        st = state_with(positions={"ABC": meta()})
        ev = run_check(S, OPEN, plan(), [], st, FakeBroker({"ABC": 47.0}, [holding()]), o)
        self.assertEqual(o.calls[:2], [("cancel", "ABC"), ("sell", "ABC", 4.0)])
        self.assertTrue(any("🛑" in e["text"] for e in ev))

    def test_target_sells_half_and_moves_stop(self):
        o = FakeOrders()
        st = state_with(positions={"ABC": meta()})
        run_check(S, OPEN, plan(), [], st, FakeBroker({"ABC": 56.5}, [holding()]), o)
        self.assertIn(("sell", "ABC", 2), o.calls)
        self.assertEqual(st["positions"]["ABC"]["stop"], 50.0)
        self.assertTrue(st["positions"]["ABC"]["half_sold"])

    def test_below_20_day_average_only_at_close(self):
        b = FakeBroker({"ABC": 49.0}, [holding()], closes={"ABC": [52.0] * 20})
        o = FakeOrders()
        run_check(S, OPEN, plan(), [], state_with(positions={"ABC": meta()}), b, o)
        self.assertNotIn(("sell", "ABC", 4.0), o.calls)
        o = FakeOrders()
        run_check(S, LATE, plan(), [], state_with(positions={"ABC": meta()}), b, o)
        self.assertIn(("sell", "ABC", 4.0), o.calls)

    def test_earnings_sell_and_plan_stop_only_moves_up(self):
        o = FakeOrders()
        st = state_with(positions={"ABC": meta()})
        run_check(S, OPEN, plan(stops={"ABC": 40.0}), [], st, FakeBroker({"ABC": 49.0}, [holding()]), o)
        self.assertEqual(st["positions"]["ABC"]["stop"], 47.5)
        run_check(S, OPEN, plan(sell_earnings=["ABC"]), [], st, FakeBroker({"ABC": 49.0}, [holding()]), o)
        self.assertIn(("sell", "ABC", 4.0), o.calls)

    def test_places_broker_stop_for_whole_shares_only(self):
        o = FakeOrders()
        run_check(S, OPEN, plan(), [], state_with(positions={"ABC": meta()}),
                  FakeBroker({"ABC": 49.0}, [holding()]), o)
        self.assertIn(("stop", "ABC", 4, 47.5), o.calls)
        o = FakeOrders()
        run_check(S, OPEN, plan(), [], state_with(positions={"ABC": meta()}),
                  FakeBroker({"ABC": 49.0}, [holding(qty="0.6")]), o)
        self.assertEqual([c for c in o.calls if c[0] == "stop"], [])

    def test_closed_loss_counts_and_trips_breaker(self):
        st = state_with(positions={"ABC": meta()}, last_prices={"ABC": 47.0}, loss_streak=2)
        ev = run_check(S, OPEN, plan(), [], st, FakeBroker({}, []), FakeOrders())
        self.assertEqual(st["loss_streak"], 3)
        self.assertTrue(st["paused"])
        self.assertTrue(any(e["type"] == "paused" for e in ev))

    def test_new_fill_takes_stop_from_pending(self):
        st = state_with(pending={"ABC": {"stop": 47.5, "target": 56.0}})
        run_check(S, OPEN, plan(), [], st, FakeBroker({"ABC": 50.0}, [holding()]), FakeOrders())
        self.assertEqual(st["positions"]["ABC"]["stop"], 47.5)
        self.assertEqual(st["pending"], {})

    def test_unknown_position_warns(self):
        st = state_with()
        ev = run_check(S, OPEN, plan(), [], st, FakeBroker({"XYZ": 10.0}, [holding("XYZ")]), FakeOrders())
        self.assertTrue(any(e["type"] == "problem" and e["symbol"] == "XYZ" for e in ev))

    def test_no_plan_warns_once_a_day(self):
        st = state_with()
        ev1 = run_check(S, OPEN, None, ["cannot read plan"], st, FakeBroker(), FakeOrders())
        ev2 = run_check(S, OPEN, None, ["cannot read plan"], st, FakeBroker(), FakeOrders())
        self.assertEqual([e["type"] for e in ev1], ["problem"])
        self.assertEqual(ev2, [])

    def test_live_mode_alerts_once_and_needs_no_orders(self):
        st = state_with(positions={"ABC": meta()})
        ev1 = run_check(LIVE, OPEN, plan(), [], st, FakeBroker({"ABC": 47.0}, [holding()]), None)
        ev2 = run_check(LIVE, OPEN, plan(), [], st, FakeBroker({"ABC": 47.0}, [holding()]), None)
        self.assertIn("Alpaca app", ev1[0]["text"])
        self.assertEqual(ev2, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and see it fail** — `python -m unittest tests.test_main -v` → `ModuleNotFoundError: robot.main`

- [ ] **Step 3: Implement** — `robot/main.py` (exits half; `# ENTRIES` is filled in by Task 6)

```python
"""One Robot check (spec §3.3). Run: python -m robot.main [--dry-run]"""
import re
from datetime import datetime, timedelta

from robot import safety


def parse_ts(s):
    """Alpaca sends nanoseconds; datetime wants at most 6 fraction digits."""
    return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", s).replace("Z", "+00:00"))


def new_state():
    return {"last_check": None, "date": None, "week": None, "week_start_equity": None,
            "loss_streak": 0, "paused": False, "pause_reason": "", "breaker_reset_seen": 0,
            "positions": {}, "pending": {}, "bought_today": [], "alerted": {}, "last_prices": {}}


def run_check(settings, clock, plan, plan_errors, state, broker, orders):
    """One check while the market is open. orders is None in live mode.
    Mutates state; returns events [{type, symbol, text}]."""
    events = []

    def ev(kind, sym, text):
        events.append({"type": kind, "symbol": sym, "text": text})

    live = settings["mode"] == "live"
    now = parse_ts(clock["timestamp"])
    today = now.date().isoformat()
    end_of_day = parse_ts(clock["next_close"]) - now <= timedelta(minutes=15)
    acct = broker.account()
    equity, cash = float(acct["equity"]), float(acct["cash"])

    def once_today(key):
        if state["alerted"].get(key) == today:
            return False
        state["alerted"][key] = today
        return True

    # -- day / week bookkeeping
    if state["date"] != today:
        state.update(date=today, bought_today=[], pending={}, alerted={})
    week = "%d-W%02d" % now.isocalendar()[:2]
    if state["week"] != week:
        state.update(week=week, week_start_equity=equity)
    if settings["breaker_reset"] > state["breaker_reset_seen"]:
        state.update(paused=False, pause_reason="", loss_streak=0, week_start_equity=equity,
                     breaker_reset_seen=settings["breaker_reset"])
        ev("resume", None, "▶️ Safety brake reset in settings — buying allowed again")
    has_plan = plan is not None
    if not has_plan and once_today("no-plan"):
        ev("problem", None, f"⚠️ No valid plan today — managing exits only ({'; '.join(plan_errors)})")
    plan = plan or {"picks": [], "cancel": [], "sell_earnings": [], "stops": {}}

    held = {p["symbol"]: p for p in broker.positions()}
    picks = {k["symbol"]: k for k in plan["picks"]}

    # -- positions closed since the last check
    for sym in [s for s in state["positions"] if s not in held]:
        m = state["positions"].pop(sym)
        # ponytail: exit = last price we saw, not the real fill; read FILL activities if this matters
        exit_px = state["last_prices"].pop(sym, m["entry"])
        if not m["sleeve"]:
            state["loss_streak"] = state["loss_streak"] + 1 if safety.is_loss(m["entry"], exit_px) else 0
        ev("closed", sym, f"{sym} closed near ${exit_px:.2f} (entry ${m['entry']:.2f})")

    # -- positions we have no notes on yet (just filled)
    for sym, p in held.items():
        if sym in state["positions"]:
            continue
        src = state["pending"].pop(sym, None) or picks.get(sym)
        m = {"entry": float(p["avg_entry_price"]), "stop": None, "target": None,
             "half_sold": False, "sleeve": False}
        if src and src.get("sleeve"):
            m["sleeve"] = True
        elif src:
            m.update(stop=src["stop"], target=src["target"])
        elif sym == settings["sleeve_symbol"]:
            m["sleeve"] = True
        else:
            ev("problem", sym, f"⚠️ {sym}: no stop on record for this position — check it")
        state["positions"][sym] = m

    # -- exits
    sold = set()

    def sell(sym, qty, why, icon):
        sold.add(sym)
        if live:
            if once_today(f"{sym}:{why}"):
                ev("alert", sym, f"{icon} {sym}: {why} — sell {qty:g} in the Alpaca app")
            return
        orders.cancel_for(sym)
        orders.sell_market(sym, qty)
        ev("sell", sym, f"{icon} {sym}: {why} — sold {qty:g} (paper)")

    for sym, m in state["positions"].items():
        qty = float(held[sym]["qty"])
        price = broker.latest_price(sym)
        state["last_prices"][sym] = price
        if m["sleeve"]:
            avg50 = safety.sma(broker.daily_closes(sym, 50, today), 50) if end_of_day else None
            if avg50 and price < avg50:
                sell(sym, qty, "closed below its 50-day average", "📉")
            continue
        new_stop = plan["stops"].get(sym)
        if new_stop and (m["stop"] is None or new_stop > m["stop"]):
            m["stop"] = new_stop  # stops only ever move up
        avg20 = safety.sma(broker.daily_closes(sym, 20, today), 20) if end_of_day else None
        if m["stop"] and price <= m["stop"]:
            sell(sym, qty, f"stop ${m['stop']:.2f} hit", "🛑")
        elif sym in plan["sell_earnings"]:
            sell(sym, qty, "earnings within 2 days", "📅")
        elif avg20 and price < avg20:
            sell(sym, qty, "below its 20-day average at the close", "📉")
        elif m["target"] and not m["half_sold"] and price >= m["target"]:
            half = safety.round_qty(qty / 2)
            m.update(half_sold=True, stop=m["entry"])
            if half > 0:
                sell(sym, half, f"target ${m['target']:.2f} hit, stop now at entry ${m['entry']:.2f}", "🎯")

    # -- broker stop orders (paper, whole shares; fractional ones are checked above every run)
    if not live:
        open_orders = orders.open_orders()
        for sym, m in state["positions"].items():
            qty = float(held[sym]["qty"])
            if sym in sold or m["sleeve"] or not m["stop"] or qty != int(qty):
                continue
            mine = [o for o in open_orders if o["symbol"] == sym and o["side"] == "sell"]
            stops = [o for o in mine if o["type"] == "stop"]
            if stops and abs(float(stops[0]["stop_price"]) - m["stop"]) < 0.005:
                continue
            if mine:
                # ponytail: stop moved -> cancel now, place the new one next check once the cancel settles
                orders.cancel_for(sym)
                continue
            orders.place_stop(sym, int(qty), m["stop"])

    # -- safety brake
    reason = safety.breaker_reason(equity, state["week_start_equity"], state["loss_streak"], settings)
    if reason and not state["paused"]:
        state.update(paused=True, pause_reason=reason)
        ev("paused", None, f"⏸️ Safety brake: {reason}. No new buys until breaker_reset is raised in settings.yaml")

    # ENTRIES

    state["last_check"] = now.isoformat()
    return events
```

- [ ] **Step 4: Run it and see it pass** — `python -m unittest tests.test_main -v` → 10 OK.

- [ ] **Step 5: Prove a test can fail.** `cp robot/main.py robot/main.py.bak`, change `new_stop > m["stop"]` to `new_stop != m["stop"]`, run → `test_earnings_sell_and_plan_stop_only_moves_up` FAILS. Then `mv robot/main.py.bak robot/main.py` and run → OK.

- [ ] **Step 6: Commit** — `git add robot/main.py tests/test_main.py && git commit -m "feat: robot check — exits, stops, breaker"`

---

### Task 6: Entries, CLI, live-mode guard

**Files:**
- Modify: `robot/main.py` (replace the `# ENTRIES` line; add `DryRunOrders` and `main()`)
- Test: add an `EntryTest` class to `tests/test_main.py`; create `tests/test_live_guard.py`

**Interfaces:**
- Consumes: `load_settings`, `load_plan`, `Broker`, `PaperOrders`, `telegram.send`
- Produces: CLI `python -m robot.main [--notebook DIR] [--dry-run]`, which writes `notebook/state.json` and appends to `notebook/trades.jsonl` (`{"time", "type", "symbol", "text"}` per line).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_main.py`, above `if __name__`:

```python
class EntryTest(unittest.TestCase):
    def test_buys_pick_at_or_below_entry(self):
        o, st = FakeOrders(), state_with()
        run_check(S, OPEN, plan(picks=[PICK]), [], st, FakeBroker({"ABC": 49.8}), o)
        self.assertEqual(o.calls, [("buy", "ABC", 4, 50.0)])
        self.assertEqual(st["pending"]["ABC"], {"stop": 47.5, "target": 56.0})
        o2 = FakeOrders()
        run_check(S, OPEN, plan(picks=[PICK]), [], st, FakeBroker({"ABC": 49.8}), o2)
        self.assertEqual(o2.calls, [])  # bought_today: no second order

    def test_waits_when_price_above_entry(self):
        o = FakeOrders()
        run_check(S, OPEN, plan(picks=[PICK]), [], state_with(), FakeBroker({"ABC": 50.5}), o)
        self.assertEqual(o.calls, [])

    def test_red_light_paused_and_cap(self):
        for p, st in [(plan(market_light="red", picks=[PICK]), state_with()),
                      (plan(picks=[PICK]), state_with(paused=True)),
                      (plan(picks=[PICK]), state_with(week_start_equity=1100.0))]:  # trips -5%
            o = FakeOrders()
            run_check(S, OPEN, p, [], st, FakeBroker({"ABC": 49.0}), o)
            self.assertEqual([c for c in o.calls if c[0] == "buy"], [])
        o = FakeOrders(open_orders=[{"symbol": s, "side": "buy", "type": "limit"} for s in ("A", "B")])
        run_check(S, OPEN, plan(market_light="yellow", picks=[PICK]), [], state_with(),
                  FakeBroker({"ABC": 49.0}), o)
        self.assertEqual([c for c in o.calls if c[0] == "buy"], [])  # yellow cap 2 already used

    def test_trend_sleeve(self):
        o = FakeOrders()
        b = FakeBroker({"SPY": 500.0}, closes={"SPY": [480.0] * 50})
        run_check(S, OPEN, plan(trend_sleeve={"hold_spy": True}), [], state_with(), b, o)
        self.assertEqual(o.calls, [("buy", "SPY", 0.6, 501.0)])

    def test_breaker_reset(self):
        st = state_with(paused=True, pause_reason="x")
        ev = run_check({**S, "breaker_reset": 1}, OPEN, plan(), [], st, FakeBroker(), FakeOrders())
        self.assertFalse(st["paused"])
        self.assertEqual(ev[0]["type"], "resume")

    def test_live_buy_is_alert_only(self):
        ev = run_check(LIVE, OPEN, plan(picks=[PICK]), [], state_with(), FakeBroker({"ABC": 49.0}), None)
        self.assertEqual(ev[0]["type"], "alert")
        self.assertIn("Alpaca app", ev[0]["text"])
```

`tests/test_live_guard.py`:

```python
"""Spec §3.3: live mode must never reach order code."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = r'''
import os, sys
from unittest import mock
import robot.main as m

class FB:
    def __init__(self, *a): pass
    def clock(self): return {"is_open": True, "timestamp": "2026-11-09T10:00:00-05:00",
                             "next_close": "2026-11-09T16:00:00-05:00"}
    def account(self): return {"equity": "1000", "cash": "1000"}
    def positions(self): return [{"symbol": "ABC", "qty": "4", "avg_entry_price": "50"}]
    def latest_price(self, s): return 40.0
    def daily_closes(self, s, n, before): return []

os.environ.update(APCA_API_KEY_ID="x", APCA_API_SECRET_KEY="y")
with mock.patch.object(m, "Broker", FB), mock.patch.object(m.telegram, "send", lambda *a: True):
    m.main(["--notebook", sys.argv[1]])
print("LOADED" if "robot.paper_orders" in sys.modules else "CLEAN")
'''
SETTINGS = (ROOT / "notebook" / "settings.yaml").read_text(encoding="utf-8").replace("mode: paper", "mode: live")
PLAN = ('{"date": "2026-11-09", "market_light": "green", "picks": '
        '[{"symbol": "XYZ", "entry_max": 50, "stop": 47.5, "target": 56, "reason": "x"}]}')


class LiveGuardTest(unittest.TestCase):
    def test_only_paper_orders_mentions_orders_endpoint(self):
        for f in (ROOT / "robot").glob("*.py"):
            if f.name != "paper_orders.py":
                self.assertNotIn("v2/orders", f.read_text(encoding="utf-8"), f.name)

    def test_live_run_never_imports_order_code(self):
        nb = pathlib.Path(tempfile.mkdtemp())
        (nb / "plan").mkdir()
        (nb / "settings.yaml").write_text(SETTINGS, encoding="utf-8")
        (nb / "plan" / "2026-11-09.json").write_text(PLAN, encoding="utf-8")
        r = subprocess.run([sys.executable, "-c", RUN, str(nb)], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip().splitlines()[-1], "CLEAN")
        self.assertIn("Alpaca app", (nb / "trades.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run them and see them fail** — `python -m unittest tests.test_main tests.test_live_guard -v` → EntryTest fails (no buys happen); the live guard errors (`main` is not defined).

- [ ] **Step 3: Implement entries.** In `robot/main.py`, replace the line `    # ENTRIES` with:

```python
    # -- entries
    if has_plan and not state["paused"]:
        open_buys = set() if live else {o["symbol"] for o in orders.open_orders() if o["side"] == "buy"}
        for sym in plan["cancel"]:
            if sym in open_buys:
                orders.cancel_for(sym)
                open_buys.discard(sym)
                ev("cancel", sym, f"✖️ {sym}: buy order cancelled (plan)")
        holding = set(state["positions"]) | open_buys
        cap = safety.max_positions_for(plan["market_light"], plan["light_falling"], settings)
        count = len(holding)
        skip = holding | set(state["bought_today"]) | set(plan["cancel"])

        def buy(sym, qty, limit, note, pending):
            nonlocal count, cash
            if live:
                ev("alert", sym, f"📋 Plan: buy {qty:g} {sym} at up to ${limit:.2f}{note} — place it in the Alpaca app")
            else:
                orders.buy_limit(sym, qty, limit)
                ev("buy", sym, f"✅ Buy order: {qty:g} {sym} at up to ${limit:.2f}{note} (paper)")
            state["pending"][sym] = pending
            state["bought_today"].append(sym)
            count += 1
            cash -= qty * limit

        sleeve = settings["sleeve_symbol"]
        if plan["trend_sleeve"]["hold_spy"] and plan["market_light"] == "green" \
                and sleeve not in skip and count < cap:
            price = broker.latest_price(sleeve)
            avg50 = safety.sma(broker.daily_closes(sleeve, 50, today), 50)
            qty = safety.round_qty(min(settings["max_position"] * equity, cash) / price)
            if avg50 and price > avg50 and qty > 0:
                buy(sleeve, qty, round(price * 1.002, 2), " (trend sleeve)", {"sleeve": True})
        for k in plan["picks"]:
            sym = k["symbol"]
            if count >= cap:
                break
            if sym in skip:
                continue
            qty = safety.position_size(equity, cash, k["entry_max"], k["stop"], settings)
            if qty <= 0:
                if once_today(f"{sym}:size"):
                    ev("skip", sym, f"{sym}: skipped — size works out to 0 (stop too far, or no cash)")
                continue
            if broker.latest_price(sym) > k["entry_max"]:
                continue  # not at our price yet; try again next check
            buy(sym, qty, k["entry_max"], f", stop ${k['stop']:.2f}", {"stop": k["stop"], "target": k["target"]})
```

- [ ] **Step 4: Add the CLI.** Change the imports at the top of `robot/main.py` to:

```python
import argparse
import json
import os
import re
from datetime import datetime, timedelta

from robot import safety, telegram
from robot.broker import Broker
from robot.plan import load_plan
from robot.settings import load_settings
```

Append at the end of the file:

```python
class DryRunOrders:
    """Stands in for PaperOrders in --dry-run: prints instead of sending."""

    def open_orders(self):
        return []

    def buy_limit(self, sym, qty, limit):
        print("DRY buy", sym, qty, limit)

    def sell_market(self, sym, qty):
        print("DRY sell", sym, qty)

    def place_stop(self, sym, qty, stop):
        print("DRY stop", sym, qty, stop)

    def cancel_for(self, sym):
        print("DRY cancel", sym)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--notebook", default="notebook")
    ap.add_argument("--dry-run", action="store_true", help="no orders, no files written, no Telegram")
    args = ap.parse_args(argv)
    nb, env = args.notebook, os.environ
    settings = load_settings(os.path.join(nb, "settings.yaml"))
    broker = Broker(settings["mode"], env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"])
    clock = broker.clock()
    if not clock["is_open"]:
        print("market closed")
        return 0
    today = parse_ts(clock["timestamp"]).date().isoformat()
    plan, plan_errors = load_plan(os.path.join(nb, "plan", f"{today}.json"), today)
    state_path = os.path.join(nb, "state.json")
    state = new_state()
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            state.update(json.load(f))
    orders = None
    if settings["mode"] == "paper":
        if args.dry_run:
            orders = DryRunOrders()
        else:
            from robot.paper_orders import PaperOrders  # only ever imported in paper mode (spec §3.3)
            orders = PaperOrders(env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"])
    events = run_check(settings, clock, plan, plan_errors, state, broker, orders)
    for e in events:
        print(e["text"])
    if args.dry_run:
        return 0
    with open(state_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(state, f, indent=2, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    with open(os.path.join(nb, "trades.jsonl"), "a", encoding="utf-8", newline="\n") as f:
        for e in events:
            f.write(json.dumps({"time": state["last_check"], **e}, ensure_ascii=False) + "\n")
    for e in events:
        telegram.send(env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID"), e["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run everything** — `python -m unittest discover -s tests -v` → all OK.

- [ ] **Step 6: Prove the guard can fail.** `cp robot/main.py robot/main.py.bak`, add `import robot.paper_orders` under the imports, run `python -m unittest tests.test_live_guard -v` → `test_live_run_never_imports_order_code` FAILS (`LOADED`). Then `mv robot/main.py.bak robot/main.py` and run → OK.

- [ ] **Step 7: Commit** — `git add robot/main.py tests && git commit -m "feat: robot entries, CLI, live-mode guard"`

---

### Task 7: GitHub Actions workflows

**Files:**
- Create: `.github/workflows/robot.yml`, `.github/workflows/tests.yml`

**Interfaces:**
- Consumes: `python -m robot.main`. Secrets: `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

- [ ] **Step 1: Write** `.github/workflows/robot.yml`

```yaml
name: robot
on:
  schedule:
    - cron: "*/15 13-21 * * 1-5"   # covers 9:00–17:45 ET in both EST and EDT; Robot exits fast when closed
  workflow_dispatch:
    inputs:
      dry_run:
        type: boolean
        default: true
concurrency:
  group: robot
  cancel-in-progress: false
permissions:
  contents: write
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    env:
      APCA_API_KEY_ID: ${{ secrets.APCA_API_KEY_ID }}
      APCA_API_SECRET_KEY: ${{ secrets.APCA_API_SECRET_KEY }}
      TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
      TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - name: Robot check
        run: python -m robot.main ${{ inputs.dry_run && '--dry-run' || '' }}
      - name: Save notebook
        if: ${{ !inputs.dry_run }}
        run: |
          git config user.name "trading-robot"
          git config user.email "trading-robot@users.noreply.github.com"
          git add notebook/state.json notebook/trades.jsonl
          git diff --cached --quiet && exit 0
          git commit -m "robot: check $(date -u +%H:%M) UTC"
          git pull --rebase && git push || (sleep 5 && git pull --rebase && git push)
      - name: Tell Ethan it failed
        if: failure()
        run: >
          curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage"
          -d chat_id="${TELEGRAM_CHAT_ID}"
          --data-urlencode text="⚠️ Robot check failed. Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }} — will retry in 15 min."
          > /dev/null
```

`.github/workflows/tests.yml`:

```yaml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - run: python -m unittest discover -s tests -v
```

- [ ] **Step 2: Check the YAML parses** — `python -c "import yaml,sys;[yaml.safe_load(open(f)) for f in sys.argv[1:]];print('ok')" .github/workflows/robot.yml .github/workflows/tests.yml` → `ok`

- [ ] **Step 3: Commit** — `git add .github && git commit -m "ci: robot schedule (every 15 min) and tests"`

The real proof is Task 11 (a manual run on GitHub). Note: the `tests` workflow runs on push, so the first push of this branch exercises it — check that it goes green.

---

### Task 8: Ignore check

**Files:**
- Modify: `.gitignore` (only if needed)

- [ ] **Step 1:** `git check-ignore -v notebook/state.json notebook/trades.jsonl || echo "not ignored"` → expect `not ignored`. The `state/` rule only matches folders. If either file shows as ignored, add `!notebook/state.json` to `.gitignore` and commit `chore: keep robot state tracked`.

---

### Task 9: Mission Control generator

**Files:**
- Create: `robot/dashboard.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Produces:
  - `render(nb: str) -> str` (HTML)
  - `render_markdown(nb: str) -> str`
  - CLI: `python -m robot.dashboard [notebook] [--markdown] > out`

- [ ] **Step 1: Write the failing test** — `tests/test_dashboard.py`

```python
import json
import os
import tempfile
import unittest

from robot.dashboard import render, render_markdown


class DashboardTest(unittest.TestCase):
    def test_empty_notebook_renders(self):
        self.assertIn("Mission Control", render(tempfile.mkdtemp()))

    def test_content_shown_and_escaped(self):
        nb = tempfile.mkdtemp()
        os.makedirs(os.path.join(nb, "plan"))
        with open(os.path.join(nb, "plan", "2026-11-09.json"), "w", encoding="utf-8") as f:
            json.dump({"market_light": "green", "fmp_calls": 42, "picks": [
                {"symbol": "ABC", "entry_max": 50, "stop": 47.5, "target": 56, "reason": "<b>x</b>"}]}, f)
        with open(os.path.join(nb, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"positions": {"XYZ": {"entry": 10, "stop": 9, "target": 12, "sleeve": False}},
                       "paused": True, "pause_reason": "3 losing trades in a row", "last_check": "t"}, f)
        page = render(nb)
        for text in ("ABC", "XYZ", "🟢", "42", "3 losing trades in a row", "&lt;b&gt;x&lt;/b&gt;"):
            self.assertIn(text, page)
        self.assertNotIn("<b>x</b>", page)
        self.assertIn("XYZ", render_markdown(nb))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and see it fail** — `python -m unittest tests.test_dashboard -v` → `ModuleNotFoundError`

- [ ] **Step 3: Implement** — `robot/dashboard.py`

```python
"""Mission Control from the notebook (spec §3.5). Claude runs this at the end of each routine.
python -m robot.dashboard [notebook] > mission-control.html
python -m robot.dashboard [notebook] --markdown > notebook/MISSION_CONTROL.md   (fallback)"""
import glob
import html
import json
import os
import sys

LIGHTS = {"green": "🟢", "yellow": "🟡", "red": "🔴"}


def _json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _latest(pattern):
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def load(nb):
    plan_file = _latest(os.path.join(nb, "plan", "*.json"))
    diary_file = _latest(os.path.join(nb, "diary", "*.md"))
    trades = []
    try:
        with open(os.path.join(nb, "trades.jsonl"), encoding="utf-8") as f:
            trades = [json.loads(line) for line in f if line.strip()][-20:]
    except (OSError, ValueError):
        pass
    diary = "No diary yet."
    if diary_file:
        with open(diary_file, encoding="utf-8") as f:
            diary = f.read()
    return {"state": _json(os.path.join(nb, "state.json"), {}),
            "plan": _json(plan_file, {}) if plan_file else {},
            "plan_date": os.path.basename(plan_file)[:-5] if plan_file else "none",
            "trades": trades[::-1], "diary": diary}


def _rows(d):
    st, plan = d["state"], d["plan"]
    picks = [(k.get("symbol"), k.get("entry_max"), k.get("stop"), k.get("target"), k.get("reason", ""))
             for k in plan.get("picks", [])]
    prices = st.get("last_prices", {})
    pos = [(s, m.get("entry"), m.get("stop") or "—", "sleeve" if m.get("sleeve") else (m.get("target") or "—"),
            prices.get(s, "—")) for s, m in st.get("positions", {}).items()]
    safety = [("Buying", "PAUSED — " + st.get("pause_reason", "") if st.get("paused") else "allowed"),
              ("Losses in a row", st.get("loss_streak", 0)),
              ("Week start equity", st.get("week_start_equity", "—")),
              ("Last Robot check", st.get("last_check") or "never"),
              ("FMP calls today (estimate)", f"{plan.get('fmp_calls', '—')} / 250")]
    return picks, pos, safety


def render(nb):
    d = load(nb)
    e = lambda x: html.escape(str(x))
    picks, pos, safety = _rows(d)

    def table(head, rows):
        h = "".join(f"<th>{e(c)}</th>" for c in head)
        b = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in r) + "</tr>" for r in rows) \
            or f"<tr><td colspan={len(head)}>none</td></tr>"
        return f"<table><tr>{h}</tr>{b}</table>"

    light = LIGHTS.get(d["plan"].get("market_light"), "⚪")
    feed = "".join(f"<li><code>{e(t.get('time', ''))}</code> {e(t.get('text', ''))}</li>" for t in d["trades"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mission Control</title>
<style>
:root{{--bg:#fafaf7;--fg:#1d1d1b;--muted:#6b6b66;--line:#e2e2dc}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#151514;--fg:#ececea;--muted:#a3a39e;--line:#2c2c2a}}}}
:root[data-theme="dark"]{{--bg:#151514;--fg:#ececea;--muted:#a3a39e;--line:#2c2c2a}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:960px;padding:16px}}
h1{{font-size:22px}} h2{{font-size:16px;margin-top:28px}} .muted{{color:var(--muted)}}
table{{border-collapse:collapse;width:100%;display:block;overflow-x:auto}}
td,th{{border-bottom:1px solid var(--line);padding:6px 10px;text-align:left}}
pre{{white-space:pre-wrap}} ul{{padding-left:18px}}
</style></head><body>
<h1>Mission Control {light}</h1>
<p class="muted">Paper money test. Plan: {e(d["plan_date"])}. Updated at each Claude run, not live.</p>
<h2>Safety</h2>{table(["", ""], safety)}
<h2>Today's plan</h2>{table(["Stock", "Buy up to", "Stop", "Target", "Why"], picks)}
<h2>Positions</h2>{table(["Stock", "Entry", "Stop", "Target", "Last price"], pos)}
<h2>Activity</h2><ul>{feed or "<li>nothing yet</li>"}</ul>
<h2>Diary</h2><pre>{e(d["diary"])}</pre>
</body></html>"""


def render_markdown(nb):
    d = load(nb)
    picks, pos, safety = _rows(d)

    def table(head, rows):
        clean = lambda c: str(c).replace("|", "/").replace("\n", " ")
        lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        return "\n".join(lines + ["| " + " | ".join(clean(c) for c in r) + " |" for r in rows])

    light = LIGHTS.get(d["plan"].get("market_light"), "⚪")
    feed = "\n".join(f"- `{t.get('time', '')}` {t.get('text', '')}" for t in d["trades"]) or "- nothing yet"
    return (f"# Mission Control {light}\n\nPlan: {d['plan_date']}\n\n## Safety\n{table(['', ''], safety)}\n\n"
            f"## Today's plan\n{table(['Stock', 'Buy up to', 'Stop', 'Target', 'Why'], picks)}\n\n"
            f"## Positions\n{table(['Stock', 'Entry', 'Stop', 'Target', 'Last price'], pos)}\n\n"
            f"## Activity\n{feed}\n\n## Diary\n\n{d['diary']}\n")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--markdown"]
    nb = args[0] if args else "notebook"
    sys.stdout.reconfigure(encoding="utf-8")
    print(render_markdown(nb) if "--markdown" in sys.argv else render(nb))
```

- [ ] **Step 4: Run it and see it pass** — `python -m unittest tests.test_dashboard -v` → 2 OK.

- [ ] **Step 5: Look at it.** `python -m robot.dashboard > "$TEMP/mc.html"`, then open it in the Browser pane at mobile width and desktop width, in light and dark. Check: no sideways scroll, readable.

- [ ] **Step 6: Commit** — `git add robot/dashboard.py tests/test_dashboard.py && git commit -m "feat: Mission Control page generator"`

---

### Task 10: Claude routine prompts

Needs the Task 0 result: pushes to `main` work, and the Artifact is either republishable or replaced by the markdown fallback.

**Files:**
- Create: `routines/plan.md`, `routines/adjust.md`, `routines/report.md`, `routines/weekly.md`

**Interfaces:**
- Consumes:
  - plan schema + `python -m robot.plan` (Task 3)
  - `python -m robot.dashboard` (Task 9)
  - skills in `.claude/skills/`

- [ ] **Step 1: Write** `routines/plan.md`

````markdown
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
````

`routines/adjust.md`:

````markdown
# Midday adjust — 12:30 ET, weekdays

Same hard rules as `routines/plan.md` (read it). Use few FMP calls: this run is a check, not a new screen.

1. `git pull`. Read today's plan, `state.json`, and today's lines in `trades.jsonl`.
2. If there's no plan for today: write one by following `routines/plan.md` steps 2–8, then stop.
3. Re-check the light (`market-breadth-analyzer`). If it got worse, update `market_light`/`light_falling`.
4. For picks not bought yet: if a pick broke down (below its stop, or its setup failed), add it to `cancel`.
5. Held positions: raise `stops` where support moved up (never lower a stop). Update `sell_earnings`.
6. Bump `version`, validate with `python -m robot.plan`, then commit `plan: <today> v<n>` and push.
7. Heartbeat check as in plan.md step 9. Telegram only if something changed or the heartbeat is stale.
8. Update Mission Control (plan.md step 11).
````

`routines/report.md`:

````markdown
# Daily report — 16:30 ET, weekdays

Same hard rules as `routines/plan.md`. No FMP calls needed.

1. `git pull`. Read today's plan, `state.json`, today's lines in `trades.jsonl`, and `settings.yaml`.
2. Write `notebook/diary/<today>.md` in plain, simple English:
   - Market light and why (one line).
   - What the Robot did today: orders, fills, stops hit, sales — copied from `trades.jsonl`, not invented.
   - Open positions: entry, stop, last price, profit/loss in $ and % (paper money).
   - Safety meter: losses in a row, week change vs `week_start_equity`, paused or not.
   - Problems: missing plan, stale heartbeat, FMP limit, Telegram failures.
   - FMP calls used today (estimate).
   - Say plainly: one day of results says nothing about whether the strategy works.
3. Commit `diary: <today>` and push.
4. Telegram "📓 Daily report: <one-line summary> — P&L today $X (paper)".
5. Update Mission Control (plan.md step 11).
````

`routines/weekly.md`:

````markdown
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
4. Commit, push, Telegram "📊 Weekly review ready", update Mission Control.
````

- [ ] **Step 2: Check that every skill named exists** —
`for s in market-breadth-analyzer uptrend-analyzer market-top-detector vcp-screener canslim-screener stockbee-momentum-burst-screener earnings-calendar data-quality-checker technical-analyst trade-performance-coach signal-postmortem; do test -d .claude/skills/$s || echo MISSING $s; done` → no output. Then prove the loop can report a miss: add `nope-skill` to the list → prints `MISSING nope-skill`.

- [ ] **Step 3: Commit** — `git add routines && git commit -m "feat: Claude routine prompts (plan, adjust, report, weekly)"`

---

### Task 11: Ethan's accounts + first real run [Ethan + Claude]

One step per message. Do every click you can. Check each result before the next step.

- [ ] **Step 1 [Ethan]:** Alpaca: sign up at alpaca.markets → Paper Trading → API Keys → Generate. Keep the page open; he pastes the keys in Step 4.
- [ ] **Step 2 [Ethan]:** FMP: sign up for the free plan at financialmodelingprep.com → copy the API key.
- [ ] **Step 3 [Ethan]:** Telegram:
  - Message @BotFather `/newbot` → copy the token.
  - Send the new bot "hi".
  - Claude opens `https://api.telegram.org/bot<token>/getUpdates` with him to read the chat id. He opens it; Claude does not type the token.
- [ ] **Step 4 [Ethan]:** GitHub repo → Settings → Secrets and variables → Actions → New secret, one at a time:
  - `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  - Claude can open the page in Chrome; Ethan types the values.
- [ ] **Step 5 [Ethan]:** Claude cloud environment for the routines:
  - Network access **Custom**, allowing:
    - `paper-api.alpaca.markets`, `api.alpaca.markets`, `data.alpaca.markets`
    - `financialmodelingprep.com`, `api.telegram.org`
    - `query1.finance.yahoo.com`, `query2.finance.yahoo.com`
  - Secrets: `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`, `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` (same values — some skills read these names), `FMP_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- [ ] **Step 6:** Push `feat/robot`. Confirm the `tests` workflow is green.
- [ ] **Step 7:** Merge to `main` (`git checkout main && git merge --no-ff feat/robot && git push`). Scheduled runs only fire from `main`.
- [ ] **Step 8:** During market hours: Actions → robot → Run workflow (dry_run = true). Check the log:
  - It says `market closed`, OR it shows a "No valid plan" message.
  - No errors.
  - Then run once with dry_run = false. The `⚠️ No valid plan today` Telegram should arrive on Ethan's phone, and a `robot: check` commit should appear.
- [ ] **Step 9 [Ethan]:** Create the 4 routines in claude.ai/code on this repo with the custom environment:
  - Plan 09:00 ET weekdays → "Follow routines/plan.md"
  - Adjust 12:30 → `routines/adjust.md`
  - Report 16:30 → `routines/report.md`
  - Weekly Saturday 10:00 → `routines/weekly.md`
- [ ] **Step 10:** Trigger the Plan routine once by hand. Confirm:
  - The plan file is committed and passes `python -m robot.plan`.
  - 📋 arrives on Telegram.
  - Mission Control is updated.
  - The next Robot check places paper buy orders. Check them in the Alpaca paper dashboard.
- [ ] **Step 11:** Check the open question from spec §7.3 (read-only Alpaca keys) in Alpaca's docs. Record the answer in `CLAUDE.md`.

---

### Task 12: Docs

**Files:**
- Modify: `CLAUDE.md` (Current Project Status, Architecture → "built", Integrations, Roadmap, Implementation Notes), `CHANGELOG.md`

- [ ] **Step 1:** Update `CLAUDE.md`:
  - How to run the tests: `python -m unittest discover -s tests -v`.
  - How to dry-run locally: `PYTHONIOENCODING=utf-8 python -m robot.main --dry-run` (needs the keys in env).
  - Where secrets live.
  - The Task 0 spike result.
  - The test week start date.
- [ ] **Step 2:** `CHANGELOG.md` entry. Commit `docs: robot built, test week starts <date>`. Push.

---

## Test week (after Task 11)

5 market days. The Weekly routine writes the report card (spec §7.2). Ethan decides about FMP paid and real money from it (spec §7.3).
