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
        # One torn line (a crashed append) must not blank the whole feed.
        with open(os.path.join(nb, "trades.jsonl"), encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    t = json.loads(line)
                except ValueError:
                    continue
                if isinstance(t, dict):
                    trades.append(t)
    except OSError:
        pass
    trades = trades[-20:]
    diary = "No diary yet."
    if diary_file:
        with open(diary_file, encoding="utf-8") as f:
            diary = f.read()
    state = _json(os.path.join(nb, "state.json"), {})
    plan = _json(plan_file, {}) if plan_file else {}
    # Hand-edited or half-written JSON can be the wrong shape; render with nothing rather than crash.
    return {"state": state if isinstance(state, dict) else {},
            "plan": plan if isinstance(plan, dict) else {},
            "plan_date": os.path.basename(plan_file)[:-5] if plan_file else "none",
            "trades": trades[::-1], "diary": diary}


def _rows(d):
    st, plan = d["state"], d["plan"]
    raw_picks = plan.get("picks")
    picks = [(k.get("symbol"), k.get("entry_max"), k.get("stop"), k.get("target"), k.get("reason", ""))
             for k in (raw_picks if isinstance(raw_picks, list) else []) if isinstance(k, dict)]
    prices = st.get("last_prices")
    prices = prices if isinstance(prices, dict) else {}
    positions = st.get("positions")
    positions = positions if isinstance(positions, dict) else {}
    pos = [(s, m.get("entry"), m.get("stop") or "—", "sleeve" if m.get("sleeve") else (m.get("target") or "—"),
            prices.get(s, "—")) for s, m in positions.items() if isinstance(m, dict)]
    safety = [("Buying", "PAUSED — " + st.get("pause_reason", "") if st.get("paused") else "allowed"),
              ("Losses in a row", st.get("loss_streak", 0)),
              ("Account at week start", _money(st.get("week_start_equity"))),
              ("Last Robot check", str(st.get("last_check") or "never")[:16].replace("T", " ")),
              ("FMP calls today (estimate)", f"{plan.get('fmp_calls', '—')} / 250")]
    return picks, pos, safety


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _money(x):
    v = _num(x)
    return "—" if v is None else f"${v:,.2f}"


def _change(now, base):
    """('up'|'down'|'flat', '+$12.00 (+1.20%)') — the sign and arrow carry direction, not just color."""
    if now is None or not base:
        return "flat", "—"
    diff = now - base
    kind = "up" if diff > 0 else "down" if diff < 0 else "flat"
    arrow = {"up": "▲", "down": "▼", "flat": "•"}[kind]
    return kind, f"{arrow} {'+' if diff >= 0 else '−'}${abs(diff):,.2f} ({diff / base:+.2%})"


LIGHT_TEXT = {"green": "Green — up to 4 positions", "yellow": "Yellow — up to 2 positions",
              "red": "Red — no new buys today"}


def render(nb):
    d = load(nb)
    e = lambda x: html.escape(str(x))
    st, plan = d["state"], d["plan"]
    picks, pos, safety = _rows(d)

    raw = st.get("equity_history")
    hist = [[str(p[0]), _num(p[1])] for p in (raw if isinstance(raw, list) else [])
            if isinstance(p, list) and len(p) == 2 and _num(p[1]) is not None]
    equity = hist[-1][1] if hist else None
    week_base = _num(st.get("week_start_equity"))
    kind, change = _change(equity, week_base)

    light_key = plan.get("market_light")
    light = LIGHTS.get(light_key, "⚪")
    lamps = "".join(f'<span class="lamp {k}{" on" if k == light_key else ""}"></span>' for k in ("red", "yellow", "green"))
    light_text = LIGHT_TEXT.get(light_key, "No plan yet — Robot manages exits only")
    if plan.get("light_falling") and light_key in ("green", "yellow"):
        light_text += ", weakening"

    def rows(items, empty):
        return "".join(items) or f'<p class="empty">{empty}</p>'

    pick_rows = rows([
        f'<div class="row"><div><b class="sym">{e(s)}</b><span class="sub">{e(why)}</span></div>'
        f'<div class="r"><span class="fig">Buy ≤ {_money(em)}</span>'
        f'<span class="sub">Stop {_money(sp)} · Target {_money(tg)}</span></div></div>'
        for s, em, sp, tg, why in picks], "No picks today. The Robot only watches what you already hold.")

    def pos_row(s, entry, stop, target, last):
        k, pct = "flat", "—"
        en, la = _num(entry), _num(last)
        if en and la is not None:
            k = "up" if la > en else "down" if la < en else "flat"
            pct = f"{'▲' if k == 'up' else '▼' if k == 'down' else '•'} {(la - en) / en:+.2%}"
        tgt = target if target == "sleeve" else _money(target) if _num(target) is not None else "—"
        return (f'<div class="row"><div><b class="sym">{e(s)}</b>'
                f'<span class="sub">Entry {_money(entry)} · Stop {_money(stop) if _num(stop) is not None else "—"}'
                f' · Target {e(tgt)}</span></div>'
                f'<div class="r"><span class="fig">{_money(last)}</span><span class="pill {k}">{pct}</span></div></div>')

    pos_rows = rows([pos_row(*p) for p in pos], "No open positions.")
    safety_rows = "".join(f'<div class="kv"><span>{e(k)}</span><b>{e(v)}</b></div>' for k, v in safety)
    feed = "".join(f'<li><time>{e(str(t.get("time", ""))[5:16].replace("T", " "))}</time>{e(t.get("text", ""))}</li>'
                   for t in d["trades"])
    data = json.dumps({"points": hist, "base": week_base}).replace("<", "\\u003c")
    hero = _money(equity) if equity is not None else "—"
    updated = str(st.get("last_check") or "never")[:16].replace("T", " ")

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mission Control</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{{--bg:#f3f5f7;--card:#ffffff;--ink:#0f1418;--muted:#5d6872;--line:#e2e6ea;--up:#0b7a32;--upline:#14a24f;--down:#c3352b;
--red:#d9473c;--yellow:#e0a100;--green:#17a34a;--off:#d5dbe0;--focus:#2563eb}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0a0d10;--card:#12171c;--ink:#edf1f4;--muted:#8b97a2;
--line:#202830;--up:#34d27a;--upline:#2fc26e;--down:#ff6d61;--off:#26303a;--focus:#7aa7ff}}}}
:root[data-theme="dark"]{{--bg:#0a0d10;--card:#12171c;--ink:#edf1f4;--muted:#8b97a2;--line:#202830;--up:#34d27a;--upline:#2fc26e;
--down:#ff6d61;--off:#26303a;--focus:#7aa7ff}}
*{{box-sizing:border-box}}
body{{background:var(--bg);color:var(--ink);font:15px/1.45 Geist,system-ui,sans-serif;margin:0}}
main{{max-width:560px;margin:0 auto;padding:20px 16px 48px}}
.fig,time,.kv b,.pill{{font-family:"Geist Mono",ui-monospace,monospace;font-variant-numeric:tabular-nums}}
.hero,.chg{{font-variant-numeric:tabular-nums}}
header{{display:flex;justify-content:space-between;align-items:baseline;gap:12px}}
.eyebrow{{font-size:13px;color:var(--muted);margin:0}} .badge{{font-size:12px;border:1px solid var(--line);border-radius:999px;padding:2px 10px;color:var(--muted)}}
.hero{{font-size:46px;font-weight:600;letter-spacing:-.03em;margin:6px 0 2px;line-height:1.1}}
.chg{{font-size:15px;margin:0}} .chg.up,.pill.up{{color:var(--up)}} .chg.down,.pill.down{{color:var(--down)}} .chg.flat,.pill.flat{{color:var(--muted)}}
.chg small{{color:var(--muted);font-family:Geist,sans-serif}}
.chart{{margin:18px -4px 6px;position:relative;outline:none;border-radius:8px}} .chart:focus-visible{{box-shadow:0 0 0 2px var(--focus)}}
.chart svg{{display:block;width:100%;height:180px;overflow:visible}}
.chart .base{{stroke:var(--muted);stroke-dasharray:2 4;stroke-width:1;opacity:.6}}
.chart .ln{{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}}
.chart.up .ln{{stroke:var(--upline)}} .chart.down .ln{{stroke:var(--down)}} .chart.flat .ln{{stroke:var(--muted)}}
.chart .cross{{stroke:var(--muted);stroke-width:1}}
.empty-chart{{height:180px;display:grid;place-items:center;text-align:center;color:var(--muted);border:1px dashed var(--line);border-radius:12px;padding:16px;font-size:14px}}
.signal{{display:flex;align-items:center;gap:14px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin-top:18px}}
.lamps{{display:flex;gap:6px;background:var(--bg);border-radius:999px;padding:5px}}
.lamp{{width:14px;height:14px;border-radius:50%;background:var(--off)}}
.lamp.on.red{{background:var(--red);box-shadow:0 0 10px var(--red)}} .lamp.on.yellow{{background:var(--yellow);box-shadow:0 0 10px var(--yellow)}}
.lamp.on.green{{background:var(--green);box-shadow:0 0 10px var(--green)}}
.signal b{{display:block;font-weight:600}} .signal span{{color:var(--muted);font-size:13px}}
h2{{font-size:13px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin:30px 0 4px}}
.row{{display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid var(--line)}}
.row>div{{min-width:0}} .r{{text-align:right;flex-shrink:0}} .sym{{font-size:16px;font-weight:600;display:block}}
.sub{{display:block;color:var(--muted);font-size:13px;overflow-wrap:anywhere}} .fig{{display:block;font-size:15px}}
.pill{{display:inline-block;font-size:13px;margin-top:2px}}
.empty{{color:var(--muted);font-size:14px;margin:8px 0}}
.kv{{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);font-size:14px}}
.kv span{{color:var(--muted)}} .kv b{{font-weight:500;text-align:right;overflow-wrap:anywhere}}
ul{{list-style:none;padding:0;margin:0}} li{{padding:8px 0;border-bottom:1px solid var(--line);font-size:14px;overflow-wrap:anywhere}}
time{{color:var(--muted);font-size:12px;margin-right:8px}}
details{{margin-top:30px}} summary{{cursor:pointer;font-weight:600}} summary:focus-visible{{outline:2px solid var(--focus);outline-offset:2px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 "Geist Mono",monospace;color:var(--muted)}}
footer{{color:var(--muted);font-size:12px;margin-top:28px}}
</style></head><body><main>
<header><p class="eyebrow">Mission Control {light}</p><span class="badge">Paper money</span></header>
<p class="hero" id="hero">{hero}</p>
<p class="chg {kind}" id="chg">{change} <small id="when">this week</small></p>
<div class="chart {kind}" id="chart" tabindex="0" role="img" aria-label="Account value over the last checks. Use left and right arrow keys to read values.">
<div class="empty-chart">The chart fills in as the Robot checks the account every 15 minutes while the market is open.</div></div>
<div class="signal"><div class="lamps" aria-hidden="true">{lamps}</div><div><b>Market light: {e(light_text)}</b><span>Plan {e(d["plan_date"])}</span></div></div>
<h2>Today's plan</h2>{pick_rows}
<h2>Positions</h2>{pos_rows}
<h2>Safety</h2>{safety_rows}
<h2>Activity</h2><ul>{feed or '<li class="empty">Nothing yet.</li>'}</ul>
<details><summary>Diary</summary><pre>{e(d["diary"])}</pre></details>
<footer>Last Robot check: {e(updated)}. This page updates after each Claude run, not live.</footer>
</main>
<script type="application/json" id="data">{data}</script>
<script>
(function(){{
  var d = JSON.parse(document.getElementById("data").textContent), pts = d.points;
  if (pts.length < 2) return;
  var box = document.getElementById("chart"), hero = document.getElementById("hero"),
      chg = document.getElementById("chg"), when = document.getElementById("when");
  var W = 600, H = 180, P = 8, vals = pts.map(function(p){{return p[1];}});
  var lo = Math.min.apply(null, vals.concat(d.base || vals[0])), hi = Math.max.apply(null, vals.concat(d.base || vals[0]));
  if (hi === lo) {{ hi += 1; lo -= 1; }}
  var x = function(i){{return i / (pts.length - 1) * W;}}, y = function(v){{return P + (hi - v) / (hi - lo) * (H - 2 * P);}};
  var ns = "http://www.w3.org/2000/svg", svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 " + W + " " + H); svg.setAttribute("preserveAspectRatio", "none");
  function el(n, a){{ var e = document.createElementNS(ns, n); for (var k in a) e.setAttribute(k, a[k]); e.setAttribute("vector-effect", "non-scaling-stroke"); svg.appendChild(e); return e; }}
  if (d.base) el("line", {{class: "base", x1: 0, x2: W, y1: y(d.base), y2: y(d.base)}});
  el("polyline", {{class: "ln", points: pts.map(function(p, i){{return x(i) + "," + y(p[1]);}}).join(" ")}});
  var cross = el("line", {{class: "cross", y1: 0, y2: H, visibility: "hidden"}});
  box.innerHTML = ""; box.appendChild(svg);
  var dot = document.createElement("span");
  dot.style.cssText = "position:absolute;width:10px;height:10px;border-radius:50%;transform:translate(-50%,-50%);visibility:hidden;pointer-events:none";
  dot.className = "dotx"; box.appendChild(dot);
  var color = getComputedStyle(box).getPropertyValue(box.classList.contains("down") ? "--down" : box.classList.contains("up") ? "--upline" : "--muted");
  dot.style.background = color; dot.style.boxShadow = "0 0 0 2px var(--card)";
  var orig = [hero.textContent, chg.className, chg.firstChild.textContent, when.textContent], cur = pts.length - 1;
  var fmt = function(v){{return "$" + v.toLocaleString("en-US", {{minimumFractionDigits: 2, maximumFractionDigits: 2}});}};
  function show(i){{
    cur = i; var p = pts[i], r = box.getBoundingClientRect(), px = x(i) / W * r.width;
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    dot.style.left = px + "px"; dot.style.top = (y(p[1]) / H * 180) + "px"; dot.style.visibility = "visible";
    hero.textContent = fmt(p[1]);
    if (d.base) {{ var diff = p[1] - d.base, k = diff > 0 ? "up" : diff < 0 ? "down" : "flat";
      chg.className = "chg " + k;
      chg.firstChild.textContent = (k == "up" ? "▲ +" : k == "down" ? "▼ −" : "• +") + fmt(Math.abs(diff)) + " (" + (diff >= 0 ? "+" : "") + (diff / d.base * 100).toFixed(2) + "%) "; }}
    when.textContent = p[0].slice(5, 16).replace("T", " ");
  }}
  function reset(){{
    cross.setAttribute("visibility", "hidden"); dot.style.visibility = "hidden"; cur = pts.length - 1;
    hero.textContent = orig[0]; chg.className = orig[1]; chg.firstChild.textContent = orig[2]; when.textContent = orig[3];
  }}
  box.addEventListener("pointermove", function(ev){{ var r = box.getBoundingClientRect();
    show(Math.max(0, Math.min(pts.length - 1, Math.round((ev.clientX - r.left) / r.width * (pts.length - 1))))); }});
  box.addEventListener("pointerleave", reset); box.addEventListener("blur", reset);
  box.addEventListener("keydown", function(ev){{
    if (ev.key == "ArrowLeft") {{ show(Math.max(0, cur - 1)); ev.preventDefault(); }}
    else if (ev.key == "ArrowRight") {{ show(Math.min(pts.length - 1, cur + 1)); ev.preventDefault(); }}
    else if (ev.key == "Escape") reset();
  }});
}})();
</script></body></html>"""


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
