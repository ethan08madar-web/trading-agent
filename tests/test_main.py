import unittest

from robot.main import new_state, run_check

S = {"mode": "paper", "risk_per_trade": 0.01, "max_position": 0.30, "max_positions": 4,
     "max_stop_distance": 0.15, "week_loss_limit": 0.05, "loss_streak_limit": 3,
     "sleeve_symbol": "SPY", "breaker_reset": 0}
LIVE = {**S, "mode": "live"}
OPEN = {"is_open": True, "timestamp": "2026-11-09T10:00:00.123456789-05:00",
        "next_close": "2026-11-09T16:00:00-05:00"}
LATE = {**OPEN, "timestamp": "2026-11-09T15:50:00-05:00"}
PICK = {"symbol": "ABC", "entry_max": 50.0, "stop": 47.5, "target": 56.0, "reason": "x"}


def plan(**kw):
    p = {"date": "2026-11-09", "market_light": "green", "light_falling": False, "picks": [],
         "cancel": [], "sell_earnings": [], "stops": {}, "trend_sleeve": {"hold_spy": False}}
    p.update(kw)
    return p


def holding(sym="ABC", qty="4", entry="50"):
    return {"symbol": sym, "qty": qty, "avg_entry_price": entry}


def meta(**kw):
    m = {"entry": 50.0, "stop": 47.5, "target": 56.0, "half_sold": False, "sleeve": False}
    m.update(kw)
    return m


class FakeBroker:
    def __init__(self, prices=None, positions=None, equity=1000.0, cash=1000.0, closes=None):
        self.prices, self.pos = prices or {}, positions or []
        self.equity, self.cash, self.closes = equity, cash, closes or {}

    def account(self):
        return {"equity": str(self.equity), "cash": str(self.cash)}

    def positions(self):
        return self.pos

    def latest_price(self, sym):
        return self.prices[sym]

    def daily_closes(self, sym, n, before):
        return self.closes.get(sym, [])[-n:]


class FakeOrders:
    def __init__(self, open_orders=None):
        self.calls, self.open = [], open_orders or []

    def open_orders(self):
        return self.open

    def buy_limit(self, s, q, l):
        self.calls.append(("buy", s, q, l))

    def sell_market(self, s, q):
        self.calls.append(("sell", s, q))

    def place_stop(self, s, q, p):
        self.calls.append(("stop", s, q, p))

    def cancel_for(self, s):
        self.calls.append(("cancel", s))


def state_with(**kw):
    st = new_state()
    st.update(date="2026-11-09", week="2026-W46", week_start_equity=1000.0)
    st.update(kw)
    return st


class ExitTest(unittest.TestCase):
    def test_stop_hit_cancels_then_sells(self):
        o = FakeOrders()
        st = state_with(positions={"ABC": meta()})
        ev = run_check(S, OPEN, plan(), [], st, FakeBroker({"ABC": 47.0}, [holding()]), o)
        self.assertEqual(o.calls[:2], [("cancel", "ABC"), ("sell", "ABC", 4.0)])
        self.assertTrue(any("🛑" in e["text"] for e in ev))

    def test_target_sells_half_and_moves_stop(self):
        o = FakeOrders()
        st = state_with(positions={"ABC": meta()})
        run_check(S, OPEN, plan(), [], st, FakeBroker({"ABC": 56.5}, [holding()]), o)
        self.assertIn(("sell", "ABC", 2), o.calls)
        self.assertEqual(st["positions"]["ABC"]["stop"], 50.0)
        self.assertTrue(st["positions"]["ABC"]["half_sold"])

    def test_below_20_day_average_only_at_close(self):
        b = FakeBroker({"ABC": 49.0}, [holding()], closes={"ABC": [52.0] * 20})
        o = FakeOrders()
        run_check(S, OPEN, plan(), [], state_with(positions={"ABC": meta()}), b, o)
        self.assertNotIn(("sell", "ABC", 4.0), o.calls)
        o = FakeOrders()
        run_check(S, LATE, plan(), [], state_with(positions={"ABC": meta()}), b, o)
        self.assertIn(("sell", "ABC", 4.0), o.calls)

    def test_earnings_sell_and_plan_stop_only_moves_up(self):
        o = FakeOrders()
        st = state_with(positions={"ABC": meta()})
        run_check(S, OPEN, plan(stops={"ABC": 40.0}), [], st, FakeBroker({"ABC": 49.0}, [holding()]), o)
        self.assertEqual(st["positions"]["ABC"]["stop"], 47.5)
        run_check(S, OPEN, plan(sell_earnings=["ABC"]), [], st, FakeBroker({"ABC": 49.0}, [holding()]), o)
        self.assertIn(("sell", "ABC", 4.0), o.calls)

    def test_places_broker_stop_for_whole_shares_only(self):
        o = FakeOrders()
        run_check(S, OPEN, plan(), [], state_with(positions={"ABC": meta()}),
                  FakeBroker({"ABC": 49.0}, [holding()]), o)
        self.assertIn(("stop", "ABC", 4, 47.5), o.calls)
        o = FakeOrders()
        run_check(S, OPEN, plan(), [], state_with(positions={"ABC": meta()}),
                  FakeBroker({"ABC": 49.0}, [holding(qty="0.6")]), o)
        self.assertEqual([c for c in o.calls if c[0] == "stop"], [])

    def test_closed_loss_counts_and_trips_breaker(self):
        st = state_with(positions={"ABC": meta()}, last_prices={"ABC": 47.0}, loss_streak=2)
        ev = run_check(S, OPEN, plan(), [], st, FakeBroker({}, []), FakeOrders())
        self.assertEqual(st["loss_streak"], 3)
        self.assertTrue(st["paused"])
        self.assertTrue(any(e["type"] == "paused" for e in ev))

    def test_new_fill_takes_stop_from_pending(self):
        st = state_with(pending={"ABC": {"stop": 47.5, "target": 56.0}})
        run_check(S, OPEN, plan(), [], st, FakeBroker({"ABC": 50.0}, [holding()]), FakeOrders())
        self.assertEqual(st["positions"]["ABC"]["stop"], 47.5)
        self.assertEqual(st["pending"], {})

    def test_unknown_position_warns(self):
        st = state_with()
        ev = run_check(S, OPEN, plan(), [], st, FakeBroker({"XYZ": 10.0}, [holding("XYZ")]), FakeOrders())
        self.assertTrue(any(e["type"] == "problem" and e["symbol"] == "XYZ" for e in ev))

    def test_no_plan_warns_once_a_day(self):
        st = state_with()
        ev1 = run_check(S, OPEN, None, ["cannot read plan"], st, FakeBroker(), FakeOrders())
        ev2 = run_check(S, OPEN, None, ["cannot read plan"], st, FakeBroker(), FakeOrders())
        self.assertEqual([e["type"] for e in ev1], ["problem"])
        self.assertEqual(ev2, [])

    def test_live_mode_alerts_once_and_needs_no_orders(self):
        st = state_with(positions={"ABC": meta()})
        ev1 = run_check(LIVE, OPEN, plan(), [], st, FakeBroker({"ABC": 47.0}, [holding()]), None)
        ev2 = run_check(LIVE, OPEN, plan(), [], st, FakeBroker({"ABC": 47.0}, [holding()]), None)
        self.assertIn("Alpaca app", ev1[0]["text"])
        self.assertEqual(ev2, [])


if __name__ == "__main__":
    unittest.main()
