"""Validate Claude's daily plan (spec §3.2). A bad plan is treated as no plan.
Claude self-checks with: python -m robot.plan notebook/plan/<date>.json <date>"""
import json
import re
import sys

SYMBOL = re.compile(r"^[A-Z][A-Z.]{0,9}$")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0


def _symbols(v):
    return isinstance(v, list) and all(isinstance(x, str) and SYMBOL.fullmatch(x) for x in v)


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
        if not isinstance(k, dict) or not isinstance(k.get("symbol"), str) or not SYMBOL.fullmatch(k["symbol"]):
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
