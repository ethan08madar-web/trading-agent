import unittest
from datetime import date, timedelta

from robot.research import check, data_problem, earnings_soon, levels, window_end

FRI = date(2026, 11, 6)


def bars(n=60, close=100.0, last_day=date(2026, 11, 5)):
    out = []
    for i in range(n):
        d = last_day - timedelta(days=n - 1 - i)
        out.append({"t": d.isoformat() + "T05:00:00Z", "h": close + 2, "l": close - 2, "c": close})
    return out


class FakeBroker:
    def __init__(self, price=100.0, history=None, fail=False):
        self.price, self.history, self.fail = price, history if history is not None else bars(), fail

    def latest_price(self, sym):
        if self.fail:
            raise OSError("https://example/?key=secret")
        return self.price

    def daily_bars(self, sym, n, before):
        return self.history[-n:]


class TestEarningsWindow(unittest.TestCase):
    def test_window_skips_weekend(self):
        self.assertEqual(window_end(FRI), date(2026, 11, 11))  # Mon, Tue, Wed

    def test_any_company_size_counts(self):
        rows = [{"symbol": "TINY", "date": "2026-11-10"}, {"symbol": "BIG", "date": "2026-11-12"}]
        self.assertEqual(earnings_soon(rows, ["TINY", "BIG"], FRI), {"TINY": "2026-11-10"})

    def test_today_counts_and_past_does_not(self):
        rows = [{"symbol": "A", "date": "2026-11-06"}, {"symbol": "B", "date": "2026-11-05"}]
        self.assertEqual(earnings_soon(rows, ["A", "B"], FRI), {"A": "2026-11-06"})


class TestDataProblem(unittest.TestCase):
    def test_good_data(self):
        self.assertIsNone(data_problem(101.0, bars(), FRI))

    def test_bad_cases(self):
        self.assertIn("no usable", data_problem(0, bars(), FRI))
        self.assertIn("only 20 days", data_problem(100, bars(20), FRI))
        self.assertIn("stops at", data_problem(100, bars(last_day=date(2026, 10, 20)), FRI))
        self.assertIn("+20%", data_problem(120, bars(), FRI))
        broken = bars()
        broken[30]["l"] = 0
        self.assertIn("zero or missing", data_problem(100, broken, FRI))


class TestLevels(unittest.TestCase):
    def test_default_levels(self):
        v = levels(100.0, bars())
        self.assertEqual((v["entry_max"], v["stop"], v["target"]), (101.0, 97.02, 108.96))
        self.assertTrue(v["stop_ok"])
        self.assertEqual((v["sma20"], v["low10"], v["high20"]), (100.0, 98.0, 102.0))

    def test_far_stop_is_flagged(self):
        b = bars()
        b[-3]["l"] = 70.0
        self.assertFalse(levels(100.0, b)["stop_ok"])


class TestCheck(unittest.TestCase):
    def test_keep_and_drop(self):
        out = check(["AAA", "ERN"], FakeBroker(), [{"symbol": "ERN", "date": "2026-11-09"}], FRI)
        self.assertTrue(out[0].startswith("KEEP AAA: last $100.00"))
        self.assertEqual(out[1], "DROP ERN: earnings 2026-11-09")

    def test_no_fmp_drops_everything(self):
        out = check(["AAA"], FakeBroker(), None, FRI)
        self.assertEqual(out, ["DROP AAA: earnings date unknown (FMP not reachable)"])

    def test_broker_error_hides_url(self):
        out = check(["AAA"], FakeBroker(fail=True), [], FRI)
        self.assertEqual(out, ["DROP AAA: price data not reachable (OSError)"])
        self.assertNotIn("secret", out[0])


if __name__ == "__main__":
    unittest.main()
