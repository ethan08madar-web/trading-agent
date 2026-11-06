"""The contestants. Each finder looks at one stock on day i (bars up to i only) and returns a
pick for tomorrow, or None. Entry/stop/target follow the bot's own rules (routines/plan.md)."""
from robot.safety import floor2


def pick(entry, stop, score, s):
    """A pick the Robot would accept: stop below entry and within max_stop_distance, target 2x risk."""
    if not entry * (1 - s["max_stop_distance"]) <= stop < entry:
        return None
    return {"entry_max": round(entry, 2), "stop": floor2(stop), "target": round(entry + 2 * (entry - stop), 2),
            "score": score}


def _uptrend(x, i):
    c, s50, s200 = x["c"][i], x["sma50"][i], x["sma200"][i]
    return bool(s50 and s200 and c > s50 > s200)


def twin(x, i, leader, s):
    """A: today's bot, mechanically. VCP-lite (uptrend, near the yearly high, last 10 days much
    calmer than the last 50) bought up to its 10-day high, or a momentum burst (+4% on more
    volume after a quiet day) bought up to +1%. Stop under the 10-day low (research.levels)."""
    c = x["c"]
    burst = (i >= 2 and c[i] >= c[i - 1] * 1.04 and x["v"][i] > x["v"][i - 1]
             and c[i - 1] < c[i - 2] * 1.04)
    vcp = (_uptrend(x, i) and x["high252"][i] and c[i] >= 0.75 * x["high252"][i]
           and x["high50"][i] and (x["high10"][i] - x["low10"][i]) < 0.5 * (x["high50"][i] - x["low50"][i]))
    if not (burst or vcp) or not x["low10"][i]:
        return None
    entry = x["high10"][i] if vcp else c[i] * 1.01
    return pick(entry, x["low10"][i] * 0.99, x["rs"][i] or 0, s)


def _above20(x, i):
    """The Robot sells anything closing below its 20-day average, so buying below it is a same-day round trip."""
    return bool(x["sma20"][i] and x["c"][i] > x["sma20"][i])


def twin_fixed(x, i, leader, s):
    """A+: today's bot, but never buying what the 20-day sell rule would sell at the same close."""
    return twin(x, i, leader, s) if _above20(x, i) else None


def pullback(x, i, leader, s):
    """B: a leader in an uptrend that has dipped back to within 3% above its 20-day average."""
    c = x["c"][i]
    if not (leader and _uptrend(x, i) and _above20(x, i) and c <= x["sma20"][i] * 1.03 and x["low10"][i]):
        return None
    return pick(c * 1.01, x["low10"][i] * 0.99, x["rs"][i], s)


def breakout(x, i, leader, s):
    """C: a leader closing above its previous 20-day high on at least 1.5x normal volume."""
    c = x["c"][i]
    if not (leader and x["prev_high20"][i] and c > x["prev_high20"][i] and x["vol50"][i]
            and x["v"][i] > 1.5 * x["vol50"][i] and x["low10"][i]):
        return None
    return pick(c * 1.01, x["low10"][i] * 0.99, x["rs"][i], s)


# The live trend sleeve: up to 30% in SPY on green days above its 50-day average, out below it.
SLEEVE = {"weight": 0.30, "entry_avg": "sma50", "exit_avg": "sma50", "need_green": True}

# params = knobs a person could tune (the backtest-expert evaluator penalises many)
BOOKS = [
    {"name": "A. Today's bot (twin)", "find": twin, "sleeve": SLEEVE, "params": 7},
    {"name": "A+. Today's bot, never buying below its 20-day average", "find": twin_fixed, "sleeve": SLEEVE,
     "params": 7},
    {"name": "B. Momentum leaders, bought on a dip", "find": pullback, "sleeve": SLEEVE, "params": 5},
    {"name": "C. Momentum leaders, bought on a breakout", "find": breakout, "sleeve": SLEEVE, "params": 5},
    {"name": "D. Trend only (SPY above its 200-day)", "find": None,
     "sleeve": {"weight": 1.0, "entry_avg": "sma200", "exit_avg": "sma200", "need_green": False}, "params": 1},
]
