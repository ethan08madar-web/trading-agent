"""The scoreboard: replay every rulebook on past years and write a plain-language report.

    python -m backtest.run            # tune years 2019-2023 only
    python -m backtest.run --final    # also the held-out years 2024 -> today (the final exam)
    python -m backtest.run --refresh  # re-download prices first

Report: backtest/results/<today>-report.md (or <today>-final.md)."""
import argparse
import os
import sys
import tempfile
from datetime import date

from backtest import data, engine, indicators, market, report
from backtest.rulebooks import BOOKS
from robot.settings import load_settings

TUNE = ("2019-01-01", "2023-12-31")
HOLDOUT = ("2024-01-01", "9999-12-31")
RESULTS = os.path.join(os.path.dirname(__file__), "results")
LIMITS = """## What this can't tell you

- **Daily prices, not 15-minute checks.** Buys and sells use each day's open/high/low/close, so fill prices are approximate. When a stop and a target could both have been hit on the same day, the replay assumes the stop (the worse case).
- **No earnings dates.** The live bot skips and sells around earnings; past earnings dates aren't free, so the replay can't. Real results may have fewer big overnight jumps, up and down.
- **No Claude.** The live bot's picks also pass through Claude's judgment and news reading. This is the rules alone.
- **Market light from prices only** (share of stocks above their 50-day average, SPY vs its 50/200-day averages). The live light also uses breadth charts.
- **Safety brake:** assumed to be switched back on the Monday after it trips. Live, it waits for you.
- **Past results don't promise future ones.** Passing means "worth paper-testing longer", not "safe with real money"."""


def load(refresh):
    rows = data.members(refresh)
    syms = sorted(set().union(*[t for d, t in rows if d >= TUNE[0]]) | {"SPY"})
    X, missing = {}, []
    for s in syms:
        b = data.bars(s, refresh)
        if len(b) > 20:
            X[s] = indicators.series(b)
        else:
            missing.append(s)
    return rows, X, missing


def period(X, rows, books_run, span, s):
    days = [d for d in X["SPY"]["t"] if span[0] <= d <= span[1]]
    mem, leaders, lights = market.prepare(X, rows, days)
    results = []
    for b in books_run:
        r = engine.run(b, X, days, lights, leaders, mem, s)
        results.append((b, report.metrics(r["equity"], r["trades"]), r))
    spy = X["SPY"]
    c0 = spy["c"][spy["idx"][days[0]]]
    bench = report.metrics([(d, 1000 * spy["c"][spy["idx"][d]] / c0) for d in days], [])
    return days, results, bench


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="also run the held-out years (the final exam)")
    ap.add_argument("--refresh", action="store_true", help="re-download prices")
    a = ap.parse_args(argv)
    s = load_settings(os.path.join(os.path.dirname(__file__), "..", "notebook", "settings.yaml"))
    rows, X, missing = load(a.refresh)
    spans = [("Tune years", TUNE)] + ([("Held-out years (final exam)", HOLDOUT)] if a.final else [])
    out_dir = tempfile.mkdtemp()
    sections, by_book = [], {b["name"]: 0 for b in BOOKS}
    for label, span in spans:
        days, results, bench = period(X, rows, BOOKS, span, s)
        rows_md = [(b["name"], m) for b, m, _ in results] + [("Benchmark: just hold SPY", bench)]
        for b, m, _ in results:
            by_book[b["name"]] += m["trades"]
        verdicts = "\n".join(f"- **{b['name']}:** {report.evaluate(m, b['params'], out_dir)}" for b, m, _ in results)
        sections.append((label, days, results, bench,
                         f"## {label}: {days[0]} to {days[-1]}\n\n{report.table(rows_md)}\n\n"
                         f"### Year by year\n\n{report.years_table(rows_md)}\n\n"
                         f"### Quality check (backtest-expert skill)\n\n{verdicts}\n"))
    if a.final:
        _, _, results, bench, _ = sections[-1]
        passed = [b["name"] for b, m, _ in results if report.passes(m, bench, by_book[b["name"]])]
        verdict = (f"**Passed the final exam:** {', '.join(passed)}." if passed else
                   "**No rulebook passed the final exam.** Just holding SPY did as well or better.")
    else:
        verdict = ("Tune years only. The held-out years (2024 → today) stay unseen until "
                   "`python -m backtest.run --final`, so they can still catch rules fitted to the past.")
    md = "\n".join([
        f"# Scoreboard — {date.today().isoformat()}", "",
        "A replay of the bot's rules on real past prices, starting each period with a pretend $1,000, "
        "using the Robot's own safety rules (1% risk per trade, at most 4 stocks, 30% cap, safety brake) "
        "and 0.10% slippage on every fill.", "",
        verdict, "",
        "**Pass mark:** better return per worst drop than SPY, no more than 2 points a year behind it, "
        f"and at least {report.MIN_TRADES} trades in total.", "",
        *[sec for *_, sec in sections],
        LIMITS, "",
        f"## Data\n\nPrices: Yahoo daily bars. Companies: everyone in the S&P 500 at any time since 2019 "
        f"({len(X) - 1} with prices). {len(missing)} have no free price history (mostly companies that were "
        f"bought out, renamed or went bust) and are left out: {', '.join(missing) or 'none'}.", ""])
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, f"{date.today().isoformat()}-{'final' if a.final else 'report'}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\nSaved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
