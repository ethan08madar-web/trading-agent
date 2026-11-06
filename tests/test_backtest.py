import operator
import random
import unittest

from backtest import data, indicators, market, rulebooks


def walk(n, seed=1, start=100.0):
    """n random-walk daily bars starting 2018-01-01 (weekdays only)."""
    from datetime import date, timedelta
    rnd, d, p, out = random.Random(seed), date(2018, 1, 1), start, []
    while len(out) < n:
        if d.weekday() < 5:
            o = p
            p = max(1.0, p * (1 + rnd.gauss(0.0005, 0.02)))
            out.append({"t": d.isoformat(), "o": o, "h": max(o, p) * 1.01, "l": min(o, p) * 0.99,
                        "c": p, "v": rnd.randint(1000, 5000)})
        d += timedelta(days=1)
    return out


class IndicatorTest(unittest.TestCase):
    def test_rolling(self):
        self.assertEqual(indicators.rolling_mean([1, 2, 3, 4, 5], 3), [None, None, 2, 3, 4])
        self.assertEqual(indicators.rolling_ext([3, 1, 4, 1, 5], 2, operator.ge), [None, 3, 4, 4, 5])
        self.assertEqual(indicators.rolling_ext([3, 1, 4, 1, 5], 2, operator.le), [None, 1, 1, 1, 1])

    def test_no_future_data(self):
        bars = walk(400)
        full = indicators.series(bars)
        for k in (60, 210, 300, 400):
            part = indicators.series(bars[:k])
            for key in full:
                if key != "idx":
                    self.assertEqual(part[key][k - 1], full[key][k - 1], f"{key} at {k} sees the future")


S = {"risk_per_trade": 0.01, "max_position": 0.30, "max_positions": 4,
     "max_stop_distance": 0.15, "week_loss_limit": 0.05, "loss_streak_limit": 3}


def fake(**cols):
    """A 3-day series with just the columns a finder test needs; the rest are None."""
    keys = ("c", "v", "sma20", "sma50", "sma200", "low10", "high10", "low50", "high50",
            "high252", "prev_high20", "vol50", "rs")
    return {k: cols.get(k, [None] * 3) for k in keys}


class RulebookTest(unittest.TestCase):
    def test_pick(self):
        self.assertIsNone(rulebooks.pick(100, 80, 1, S))  # stop 20% away: the Robot would refuse it
        self.assertEqual(rulebooks.pick(100, 95, 1, S),
                         {"entry_max": 100, "stop": 95, "target": 110, "score": 1})

    def test_breakout_needs_leader_high_and_volume(self):
        x = fake(c=[100, 100, 110], prev_high20=[None, None, 105], v=[1000, 1000, 3000],
                 vol50=[1000, 1000, 1000], low10=[95, 95, 98], rs=[0.5, 0.5, 0.5])
        k = rulebooks.breakout(x, 2, True, S)
        self.assertEqual((k["entry_max"], k["stop"]), (111.1, 97.02))
        self.assertIsNone(rulebooks.breakout(x, 2, False, S))
        x["v"][2] = 1200
        self.assertIsNone(rulebooks.breakout(x, 2, True, S))

    def test_twin_momentum_burst(self):
        x = fake(c=[100, 101, 106], v=[1000, 1000, 2000], low10=[95, 95, 96], rs=[None, None, 0.2])
        self.assertIsNotNone(rulebooks.twin(x, 2, False, S))
        x["v"][2] = 900  # no extra volume: not a burst
        self.assertIsNone(rulebooks.twin(x, 2, False, S))


class LightTest(unittest.TestCase):
    def test_light(self):
        self.assertEqual(market.market_light(90, 95, 100, 0.7, 0.7), ("red", False))     # SPY under 200-day
        self.assertEqual(market.market_light(110, 100, 100, 0.30, 0.30), ("red", False))  # weak breadth
        self.assertEqual(market.market_light(110, 100, 100, 0.60, 0.60), ("green", False))
        self.assertEqual(market.market_light(110, 100, 100, 0.45, 0.45), ("yellow", False))
        self.assertEqual(market.market_light(110, 100, 100, 0.56, 0.65), ("green", True))  # breadth falling


class DataTest(unittest.TestCase):
    def test_members_on(self):
        rows = data.load_members('date,tickers\n2017-05-01,"OLD"\n2019-01-02,"A,B"\n2019-03-01,"A,C"\n')
        self.assertEqual(len(rows), 2)  # rows before 2018 dropped
        self.assertEqual(data.members_on(rows, "2019-02-15"), {"A", "B"})
        self.assertEqual(data.members_on(rows, "2019-03-01"), {"A", "C"})
        self.assertEqual(data.members_on(rows, "2018-12-31"), set())

    def test_yahoo_bars_adjusts_and_drops_bad_rows(self):
        p = {"chart": {"result": [{"timestamp": [1546439400, 1546525800],
             "indicators": {"quote": [{"open": [100, None], "high": [110, 1], "low": [90, 1],
                                       "close": [100, 1], "volume": [5, 1]}],
                            "adjclose": [{"adjclose": [50, 1]}]}}]}}
        self.assertEqual(data.yahoo_bars(p), [{"t": "2019-01-02", "o": 50, "h": 55, "l": 45, "c": 50, "v": 5}])


if __name__ == "__main__":
    unittest.main()
