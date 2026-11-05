"""One Robot check (spec §3.3). Run: python -m robot.main [--dry-run]"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

from robot import safety, telegram
from robot.broker import Broker
from robot.plan import load_plan
from robot.settings import load_settings


def parse_ts(s):
    """Alpaca sends nanoseconds; datetime wants at most 6 fraction digits."""
    return datetime.fromisoformat(re.sub(r"(\.\d{6})\d+", r"\1", s).replace("Z", "+00:00"))


def new_state():
    return {"last_check": None, "date": None, "week": None, "week_start_equity": None,
            "loss_streak": 0, "paused": False, "pause_reason": "", "breaker_reset_seen": 0,
            "positions": {}, "pending": {}, "bought_today": [], "alerted": {}, "last_prices": {}}


def run_check(settings, clock, plan, plan_errors, state, broker, orders, events=None):
    """One check while the market is open. orders is None in live mode.
    Mutates state; appends to and returns events [{type, symbol, text}] (the caller can pass
    its own list so events survive a crash)."""
    events = [] if events is None else events

    def ev(kind, sym, text):
        events.append({"type": kind, "symbol": sym, "text": text})

    def attempt(sym, what, fn, *args):
        """One order call; a failure is reported and the check carries on. No exception text:
        it can contain URLs."""
        try:
            fn(*args)
            return True
        except Exception as e:
            ev("failed", sym, f"❌ {sym}: {what} failed ({type(e).__name__}) — will retry next check")
            return False

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
        state.update(date=today, bought_today=[], alerted={})
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
        last = state["last_prices"].pop(sym, m["entry"])
        # a broker stop can fill below the last price we saw; our own sells record their price
        exit_px = m.get("exit_price") or (min(last, m["stop"]) if m["stop"] else last)
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
        state["positions"][sym] = m
        ev("filled", sym, f"📥 {sym}: filled {float(p['qty']):g} at ${m['entry']:.2f}")

    # -- buys that never filled: forget them (kept across midnight so a late fill still gets its stop)
    open_buys = set() if live else {o["symbol"] for o in orders.open_orders() if o["side"] == "buy"}
    for sym in list(state["pending"]):
        if live:  # no open-order list in live mode
            since = datetime.fromisoformat(state["pending"][sym].get("since", today)).date()
            gone = (now.date() - since).days >= 3
        else:
            gone = sym not in open_buys
        if gone:
            del state["pending"][sym]

    # -- exits
    sold = set()

    def sell(sym, qty, why, icon, price):
        """True if the sell went out (live: was alerted)."""
        if live:
            if once_today(f"{sym}:{why}"):
                ev("alert", sym, f"{icon} {sym}: {why} — sell {qty:g} in the Alpaca app")
        elif not (attempt(sym, "cancelling its orders", orders.cancel_for, sym)
                  and attempt(sym, "sell", orders.sell_market, sym, qty)):
            return False
        else:
            ev("sell", sym, f"{icon} {sym}: {why} — sold {qty:g} (paper)")
        sold.add(sym)
        if qty == float(held[sym]["qty"]):
            state["positions"][sym]["exit_price"] = price  # full exit: the price we sold at
            state["bought_today"].append(sym)  # a stopped-out stock is not re-bought today
        return True

    for sym, m in state["positions"].items():
        qty = float(held[sym]["qty"])
        m.pop("exit_price", None)  # only a sell from this check counts
        price = broker.latest_price(sym)
        if price <= 0:  # bad data (spec 5): never act on it
            if once_today(f"{sym}:price"):
                ev("problem", sym, f"⚠️ {sym}: no usable price from the broker — skipping it this check")
            continue
        state["last_prices"][sym] = price
        if not m["half_sold"]:
            m["entry"] = float(held[sym]["avg_entry_price"])  # a partial fill moves the average
        if m["sleeve"]:
            avg50 = safety.sma(broker.daily_closes(sym, 50, today), 50) if end_of_day else None
            if avg50 and price < avg50:
                sell(sym, qty, "closed below its 50-day average", "📉", price)
            continue
        new_stop = plan["stops"].get(sym)
        if new_stop and (m["stop"] is None or new_stop > m["stop"]):
            m["stop"] = new_stop  # stops only ever move up
        if m["stop"] is None:  # every check, so it cannot go quiet
            ev("problem", sym, f"⚠️ {sym}: no stop on record for this position — check it")
        avg20 = safety.sma(broker.daily_closes(sym, 20, today), 20) if end_of_day else None
        if m["stop"] and price <= m["stop"]:
            sell(sym, qty, f"stop ${m['stop']:.2f} hit", "🛑", price)
        elif sym in plan["sell_earnings"]:
            sell(sym, qty, "earnings within 2 days", "📅", price)
        elif avg20 and price < avg20:
            sell(sym, qty, "below its 20-day average at the close", "📉", price)
        elif m["target"] and not m["half_sold"] and price >= m["target"]:
            half = safety.round_qty(qty / 2)
            if half <= 0 or sell(sym, half, f"target ${m['target']:.2f} hit, stop now at entry ${m['entry']:.2f}",
                                 "🎯", price):
                m.update(half_sold=True, stop=m["entry"])

    # -- broker stop orders (paper, whole shares; fractional ones are checked above every run)
    if not live:
        open_orders = orders.open_orders()
        for sym, m in state["positions"].items():
            qty = float(held[sym]["qty"])
            if sym in sold or m["sleeve"] or not m["stop"] or qty != int(qty):
                continue
            mine = [o for o in open_orders if o["symbol"] == sym and o["side"] == "sell"]
            stops = [o for o in mine if o["type"] == "stop"]
            if stops and abs(float(stops[0]["stop_price"]) - m["stop"]) < 0.005 \
                    and int(float(stops[0]["qty"])) == int(qty):
                continue
            if mine:
                # ponytail: stop moved -> cancel now, place the new one next check once the cancel settles
                attempt(sym, "cancelling its old stop", orders.cancel_for, sym)
                continue
            attempt(sym, "placing its stop", orders.place_stop, sym, int(qty), m["stop"])

    # -- safety brake
    reason = safety.breaker_reason(equity, state["week_start_equity"], state["loss_streak"], settings)
    if reason and not state["paused"]:
        state.update(paused=True, pause_reason=reason)
        ev("paused", None, f"⏸️ Safety brake: {reason}. No new buys until breaker_reset is raised in settings.yaml")

    # -- entries
    if has_plan and not state["paused"]:
        for sym in plan["cancel"]:
            if sym in open_buys and attempt(sym, "cancelling its buy order", orders.cancel_for, sym):
                open_buys.discard(sym)
                ev("cancel", sym, f"✖️ {sym}: buy order cancelled (plan)")
        holding = set(state["positions"]) | open_buys
        cap = safety.max_positions_for(plan["market_light"], plan["light_falling"], settings)
        count = len(holding)
        skip = holding | set(state["bought_today"]) | set(plan["cancel"])

        def buy(sym, qty, limit, note, pending):
            nonlocal count, cash
            if live:
                ev("alert", sym, f"📋 Plan: buy {qty:g} {sym} at up to ${limit:.2f}{note} — place it in the Alpaca app")
            elif attempt(sym, "buy order", orders.buy_limit, sym, qty, limit):
                ev("buy", sym, f"✅ Buy order: {qty:g} {sym} at up to ${limit:.2f}{note} (paper)")
            else:
                return
            state["pending"][sym] = {**pending, "since": today}
            state["bought_today"].append(sym)
            count += 1
            cash -= qty * limit

        sleeve = settings["sleeve_symbol"]
        if plan["trend_sleeve"]["hold_spy"] and plan["market_light"] == "green" \
                and sleeve not in skip and count < cap:
            price = broker.latest_price(sleeve)
            avg50 = safety.sma(broker.daily_closes(sleeve, 50, today), 50)
            qty = safety.round_qty(min(settings["max_position"] * equity, cash) / price)
            if avg50 and price > avg50 and qty > 0:
                buy(sleeve, qty, round(price * 1.002, 2), " (trend sleeve)", {"sleeve": True})
        for k in plan["picks"]:
            sym = k["symbol"]
            if count >= cap:
                break
            if sym in skip:
                continue
            qty = safety.position_size(equity, cash, k["entry_max"], k["stop"], settings)
            if qty <= 0:
                if once_today(f"{sym}:size"):
                    ev("skip", sym, f"{sym}: skipped — size works out to 0 (stop too far, or no cash)")
                continue
            price = broker.latest_price(sym)
            if not k["stop"] < price <= k["entry_max"]:
                continue  # not at our price yet (or already through the stop); try again next check
            buy(sym, qty, k["entry_max"], f", stop ${k['stop']:.2f}", {"stop": k["stop"], "target": k["target"]})

    state["last_check"] = now.isoformat()
    return events


class DryRunOrders:
    """Stands in for PaperOrders in --dry-run: prints instead of sending."""

    def open_orders(self):
        return []

    def buy_limit(self, sym, qty, limit):
        print("DRY buy", sym, qty, limit)

    def sell_market(self, sym, qty):
        print("DRY sell", sym, qty)

    def place_stop(self, sym, qty, stop):
        print("DRY stop", sym, qty, stop)

    def cancel_for(self, sym):
        print("DRY cancel", sym)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")  # emoji in event text; Windows consoles default to cp1252
    ap = argparse.ArgumentParser()
    ap.add_argument("--notebook", default="notebook")
    ap.add_argument("--dry-run", action="store_true", help="no orders, no files written, no Telegram")
    args = ap.parse_args(argv)
    nb, env = args.notebook, os.environ
    settings = load_settings(os.path.join(nb, "settings.yaml"))
    broker = Broker(settings["mode"], env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"])
    clock = broker.clock()
    if not clock["is_open"]:
        print("market closed")
        return 0
    today = parse_ts(clock["timestamp"]).date().isoformat()
    plan, plan_errors = load_plan(os.path.join(nb, "plan", f"{today}.json"), today)
    state_path = os.path.join(nb, "state.json")
    state = new_state()
    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            state.update(json.load(f))
    orders = None
    if settings["mode"] == "paper":
        if args.dry_run:
            orders = DryRunOrders()
        else:
            from robot.paper_orders import PaperOrders  # only ever imported in paper mode (spec §3.3)
            orders = PaperOrders(env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"])
    events = []  # filled in place so the finally block can log them even if run_check raises
    try:
        run_check(settings, clock, plan, plan_errors, state, broker, orders, events)
    finally:
        # saved even if run_check raised: an order may already have gone out
        if not args.dry_run:
            tmp = state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as f:
                json.dump(state, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, state_path)
            if events:
                with open(os.path.join(nb, "trades.jsonl"), "a", encoding="utf-8", newline="\n") as f:
                    for e in events:
                        f.write(json.dumps({"time": state["last_check"], **e}, ensure_ascii=False) + "\n")
    for e in events:
        print(e["text"])
    if args.dry_run:
        return 0
    for e in events:
        telegram.send(env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID"), e["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
