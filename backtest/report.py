"""Scoreboard numbers and the plain-language report."""
import os
import subprocess
import sys

MIN_TRADES = 100
EVALUATOR = os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "backtest-expert",
                         "scripts", "evaluate_backtest.py")


def drawdown(values):
    """Worst fall from a high point, as a fraction (0.25 = -25%)."""
    peak, worst = values[0], 0.0
    for v in values:
        peak = max(peak, v)
        worst = max(worst, 1 - v / peak)
    return worst


def metrics(curve, trades):
    vals = [v for _, v in curve]
    years = len(vals) / 252
    cagr = (vals[-1] / vals[0]) ** (1 / years) - 1
    dd = drawdown(vals)
    wins = [t["pnl_pct"] for t in trades if t["pnl_pct"] > 0]
    losses = [-t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0]
    by_year, prev = {}, vals[0]
    for (day, v), nxt in zip(curve, curve[1:] + [(None, None)]):
        if nxt[0] is None or nxt[0][:4] != day[:4]:
            by_year[day[:4]] = v / prev - 1
            prev = v
    return {"end": vals[-1], "cagr": cagr, "dd": dd, "ratio": cagr / dd if dd else float("inf"),
            "trades": len(trades), "win_rate": len(wins) / len(trades) if trades else 0.0,
            "avg_win": sum(wins) / len(wins) if wins else 0.0,
            "avg_loss": sum(losses) / len(losses) if losses else 0.0,
            "years": years, "by_year": by_year}


def passes(m, spy, total_trades):
    """Spec pass mark: smoother than SPY per unit of return, at most 2 points/year behind it, enough trades."""
    return m["ratio"] > spy["ratio"] and m["cagr"] >= spy["cagr"] - 0.02 and total_trades >= MIN_TRADES


def evaluate(m, params, out_dir):
    """The backtest-expert skill's verdict line(s), or a note if it couldn't run."""
    if not m["trades"]:
        return "not evaluated (no trades)"
    cmd = [sys.executable, EVALUATOR, "--total-trades", str(m["trades"]),
           "--win-rate", f"{m['win_rate'] * 100:.1f}", "--avg-win-pct", f"{m['avg_win'] * 100:.2f}",
           "--avg-loss-pct", f"{max(m['avg_loss'] * 100, 0.01):.2f}", "--max-drawdown-pct", f"{m['dd'] * 100:.1f}",
           "--years-tested", str(max(1, round(m["years"]))), "--num-parameters", str(params),
           "--slippage-tested", "--output-dir", out_dir]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    lines = [l for l in r.stdout.splitlines() if not l.startswith(("JSON:", "Markdown:"))]
    return " / ".join(l.strip() for l in lines if l.strip()) or "evaluator gave no output"


def pct(x):
    return f"{x * 100:+.1f}%"


def table(rows):
    """rows: [(name, metrics)] -> markdown table."""
    out = ["| Rulebook | $1,000 became | Per year | Worst drop | Return ÷ drop | Trades | Wins | Avg win | Avg loss |",
           "|---|---|---|---|---|---|---|---|---|"]
    for name, m in rows:
        out.append(f"| {name} | ${m['end']:,.0f} | {pct(m['cagr'])} | -{m['dd'] * 100:.1f}% | {m['ratio']:.2f} | "
                   f"{m['trades']} | {m['win_rate'] * 100:.0f}% | {pct(m['avg_win'])} | -{m['avg_loss'] * 100:.1f}% |")
    return "\n".join(out)


def years_table(rows):
    years = sorted({y for _, m in rows for y in m["by_year"]})
    out = ["| Rulebook | " + " | ".join(years) + " |", "|---|" + "---|" * len(years)]
    for name, m in rows:
        out.append(f"| {name} | " + " | ".join(pct(m["by_year"].get(y, 0)) for y in years) + " |")
    return "\n".join(out)
