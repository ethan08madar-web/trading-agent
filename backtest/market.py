"""Market light and strongest stocks for each replay day, from prices alone.
(The live bot also reads breadth charts and uses Claude's judgment; the replay can't.)"""
from backtest.data import members_on

LEADER_SHARE = 0.10  # top 10% by strength count as leaders


def market_light(close, sma50, sma200, breadth, breadth_5d_ago):
    """(light, light_falling). breadth = share of index stocks above their 50-day average."""
    if sma200 is None or close < sma200 or breadth < 0.35:
        light = "red"
    elif sma50 and close > sma50 and breadth >= 0.55:
        light = "green"
    else:
        light = "yellow"
    return light, breadth < breadth_5d_ago - 0.05


def prepare(X, rows, days):
    """Per day: index members with data, leaders, (light, falling). X: {sym: series}, must hold SPY."""
    members_by_day, leaders, lights, hist = {}, {}, {}, []
    spy = X["SPY"]
    for day in days:
        mem = {t for t in members_on(rows, day) if t in X and day in X[t]["idx"]}
        members_by_day[day] = mem
        at = {t: X[t]["idx"][day] for t in mem}
        above = [X[t]["c"][j] > X[t]["sma50"][j] for t, j in at.items() if X[t]["sma50"][j]]
        b = sum(above) / len(above) if above else 0.0
        hist.append(b)
        j = spy["idx"][day]
        lights[day] = market_light(spy["c"][j], spy["sma50"][j], spy["sma200"][j], b,
                                   hist[-6] if len(hist) >= 6 else b)
        rs = sorted((X[t]["rs"][j], t) for t, j in at.items() if X[t]["rs"][j] is not None)
        leaders[day] = {t for _, t in rs[int(len(rs) * (1 - LEADER_SHARE)):]}
    return members_by_day, leaders, lights
