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
