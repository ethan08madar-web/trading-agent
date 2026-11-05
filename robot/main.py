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
