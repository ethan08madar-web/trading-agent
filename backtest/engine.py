"""Day-by-day replay of one rulebook with a pretend account, using the Robot's own rules
(robot/safety.py). Orders are planned after each close and can fill the next day."""
from datetime import date

from robot import safety

SLIP = 0.001  # 0.10% worse price on every fill


def week_of(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def run(book, X, days, lights, leaders, members_by_day, s, start_cash=1000.0):
    """book: a rulebooks.BOOKS entry; X: {sym: indicators.series}; days: trading dates in order;
    lights {day: (light, falling)}, leaders {day: set}, members_by_day {day: set} from market.prepare.
    Returns {"equity": [(day, value)], "trades": [{symbol, in, out, entry, exit, pnl_pct, why, sleeve}]}."""
    cash, pos, orders, trades, curve, last_close = start_cash, {}, {}, [], [], {}
    st = {"loss_streak": 0, "paused": False, "paused_week": None, "week": None, "week_start": None}
    sl = book.get("sleeve")

    def at(sym, day):
        x = X.get(sym)
        j = x["idx"].get(day) if x else None
        return (x, j) if j is not None else (None, None)

    def sell(sym, m, qty, px):
        nonlocal cash
        cash += qty * px
        m["proceeds"] += qty * px
        m["qty"] -= qty

    def close_out(sym, m, px, day, why):
        sell(sym, m, m["qty"], px)
        trades.append({"symbol": sym, "in": m["day_in"], "out": day, "entry": m["entry"], "exit": px,
                       "pnl_pct": m["proceeds"] / m["cost"] - 1, "why": why, "sleeve": m["sleeve"]})
        if not m["sleeve"]:
            st["loss_streak"] = st["loss_streak"] + 1 if safety.is_loss(m["cost"], m["proceeds"]) else 0
        del pos[sym]

    for day in days:
        # 1. yesterday's orders fill today
        for sym, o in orders.items():
            x, j = at(sym, day)
            if x is None or sym in pos:
                continue
            op = x["o"][j]
            if o.get("at_open"):
                px = op
            elif op <= o["stop"] or x["l"][j] > o["entry_max"]:
                continue  # already through the stop, or never came down to our price
            else:
                px = min(op, o["entry_max"])
            px *= 1 + SLIP
            qty = safety.round_qty(min(o["qty"], cash / px))
            if qty <= 0:
                continue
            cash -= qty * px
            pos[sym] = {"qty": qty, "entry": px, "stop": o.get("stop"), "target": o.get("target"),
                        "half_sold": False, "sleeve": o.get("sleeve", False), "day_in": day,
                        "cost": qty * px, "proceeds": 0.0}
        orders = {}

        # 2. exits on today's bar (a stock bought today can be stopped out today: the worst case)
        for sym in list(pos):
            m = pos[sym]
            x, j = at(sym, day)
            if x is None:
                if day > X[sym]["t"][-1]:  # stopped trading (bought out, delisted)
                    close_out(sym, m, last_close.get(sym, m["entry"]), day, "data ended")
                continue
            op, hi, lo, c = x["o"][j], x["h"][j], x["l"][j], x["c"][j]
            if m["sleeve"]:
                avg = x[sl["exit_avg"]][j]
                if avg and c < avg:
                    close_out(sym, m, c * (1 - SLIP), day, f"closed below its {sl['exit_avg'][3:]}-day average")
                continue
            why = safety.exit_reason(m, lo, hi, c, x["sma20"][j])
            if why == "stop":
                close_out(sym, m, min(op, m["stop"]) * (1 - SLIP), day, "stop")
            elif why == "avg20":
                close_out(sym, m, c * (1 - SLIP), day, "below 20-day average")
            elif why == "target":
                half = safety.round_qty(m["qty"] / 2)
                if half > 0:
                    sell(sym, m, half, max(op, m["target"]) * (1 - SLIP))
                m.update(half_sold=True, stop=m["entry"])

        # 3. value the account; weekly start value; safety brake
        for sym in pos:
            x, j = at(sym, day)
            if x is not None:
                last_close[sym] = x["c"][j]
        equity = cash + sum(m["qty"] * last_close.get(sym, m["entry"]) for sym, m in pos.items())
        curve.append((day, equity))
        wk = week_of(day)
        if wk != st["week"]:
            st.update(week=wk, week_start=equity)
            if st["paused"] and st["paused_week"] != wk:
                # ponytail: assumes Ethan resets the brake the Monday after it trips; live it waits for him
                st.update(paused=False, loss_streak=0)
        if not st["paused"] and safety.breaker_reason(equity, st["week_start"], st["loss_streak"], s):
            st.update(paused=True, paused_week=wk)
        if st["paused"]:
            continue

        # 4. tomorrow's orders: sleeve first, then the best picks while under the light's cap
        light, falling = lights[day]
        cap = safety.max_positions_for(light, falling, s)
        count, avail = len(pos), cash
        spy, j = at("SPY", day)
        if sl and "SPY" not in pos and spy is not None and spy[sl["entry_avg"]][j] \
                and spy["c"][j] > spy[sl["entry_avg"]][j] \
                and (not sl["need_green"] or (light == "green" and count < cap)):
            qty = safety.round_qty(min(sl["weight"] * equity, avail) / (spy["c"][j] * 1.02))  # room for a gap up
            if qty > 0:
                orders["SPY"] = {"qty": qty, "at_open": True, "sleeve": True}
                avail -= qty * spy["c"][j] * 1.02
                count += 1
        if book.get("find"):
            cands = []
            for sym in members_by_day[day]:
                if sym in pos or sym == "SPY":
                    continue
                x, j = at(sym, day)
                k = book["find"](x, j, sym in leaders[day], s)
                if k:
                    cands.append((k["score"], sym, k))
            for _, sym, k in sorted(cands, key=lambda c: (c[0], c[1]), reverse=True):
                if count >= cap:
                    break
                qty = safety.position_size(equity, avail, k["entry_max"], k["stop"], s)
                if qty <= 0:
                    continue
                orders[sym] = {**k, "qty": qty}
                avail -= qty * k["entry_max"]
                count += 1
    return {"equity": curve, "trades": trades}
