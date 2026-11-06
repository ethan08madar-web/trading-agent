"""Trailing-only price facts per stock. Every value at day i uses bars up to i, never later."""
import operator
from collections import deque


def rolling_mean(xs, n):
    out, s = [], 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        out.append(s / n if i >= n - 1 else None)
    return out


def rolling_ext(xs, n, better):
    """Trailing n-day max (better=operator.ge) or min (operator.le), in one pass."""
    q, out = deque(), []
    for i, x in enumerate(xs):
        while q and better(x, xs[q[-1]]):
            q.pop()
        q.append(i)
        if q[0] <= i - n:
            q.popleft()
        out.append(xs[q[0]] if i >= n - 1 else None)
    return out


def series(bars):
    o, h, l, c, v = ([b[k] for b in bars] for k in "ohlcv")
    hi20 = rolling_ext(h, 20, operator.ge)
    x = {"t": [b["t"] for b in bars], "o": o, "h": h, "l": l, "c": c, "v": v,
         "sma20": rolling_mean(c, 20), "sma50": rolling_mean(c, 50), "sma200": rolling_mean(c, 200),
         "low10": rolling_ext(l, 10, operator.le), "high10": rolling_ext(h, 10, operator.ge),
         "low50": rolling_ext(l, 50, operator.le), "high50": rolling_ext(h, 50, operator.ge),
         "high252": rolling_ext(h, 252, operator.ge),
         "prev_high20": [None] + hi20[:-1],  # the 20 days before today, for breakouts
         "vol50": rolling_mean(v, 50),
         # strength: half the 6-month return plus half the 12-month return
         "rs": [0.5 * (c[i] / c[i - 126] - 1) + 0.5 * (c[i] / c[i - 252] - 1) if i >= 252 else None
                for i in range(len(c))]}
    x["idx"] = {t: i for i, t in enumerate(x["t"])}
    return x
