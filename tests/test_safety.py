import unittest

from robot import safety

S = {"risk_per_trade": 0.01, "max_position": 0.30, "max_positions": 4,
     "max_stop_distance": 0.15, "week_loss_limit": 0.05, "loss_streak_limit": 3}


class SizeTest(unittest.TestCase):
    def test_cash_is_the_tightest_cap(self):
        # risk 10/2.5 = 4 shares, 30% cap 6, cash 1000/50 = 20 -> 4
        self.assertEqual(safety.position_size(1000, 1000, 50, 47.5, S), 4)

    def test_30_percent_cap_wins(self):
        # risk 10/7.5 = 1.33, cap 300/231.5 = 1.29 -> whole share 1
        self.assertEqual(safety.position_size(1000, 1000, 231.5, 224, S), 1)

    def test_fractional_below_one_share(self):
        # risk 10/10 = 1, cap 300/500 = 0.6 -> 0.6
        self.assertEqual(safety.position_size(1000, 1000, 500, 490, S), 0.6)

    def test_rejects(self):
        self.assertEqual(safety.position_size(1000, 1000, 100, 100, S), 0)  # stop not below entry
        self.assertEqual(safety.position_size(1000, 1000, 100, 80, S), 0)   # stop 20% away > 15%
        self.assertEqual(safety.position_size(1000, 0, 50, 47.5, S), 0)     # no cash

    def test_floor2_float_safe(self):
        self.assertEqual(safety.floor2(0.29), 0.29)
        self.assertEqual(safety.round_qty(0.296), 0.29)


class RulesTest(unittest.TestCase):
    def test_light_caps(self):
        self.assertEqual(safety.max_positions_for("green", False, S), 4)
        self.assertEqual(safety.max_positions_for("yellow", False, S), 2)
        self.assertEqual(safety.max_positions_for("yellow", True, S), 0)
        self.assertEqual(safety.max_positions_for("red", False, S), 0)

    def test_breaker(self):
        self.assertIsNone(safety.breaker_reason(1000, 1000, 0, S))
        self.assertIn("this week", safety.breaker_reason(1000, 1100, 0, S))   # -9.1%
        self.assertIsNone(safety.breaker_reason(1000, 1050, 0, S))           # -4.8%
        self.assertIn("in a row", safety.breaker_reason(1000, 1000, 3, S))

    def test_is_loss_and_sma(self):
        self.assertTrue(safety.is_loss(50, 47))
        self.assertFalse(safety.is_loss(50, 49.9))   # stop at entry, small slip: not a loss
        self.assertEqual(safety.sma([1, 2, 3, 4], 2), 3.5)
        self.assertIsNone(safety.sma([1], 2))


class ExitTest(unittest.TestCase):
    def test_order(self):
        m = {"stop": 90, "target": 120, "half_sold": False}
        self.assertEqual(safety.exit_reason(m, 89, 125, 100, 110), "stop")  # stop beats everything
        self.assertEqual(safety.exit_reason(m, 95, 125, 100, None, True), "earnings")
        self.assertEqual(safety.exit_reason(m, 95, 125, 100, 110), "avg")
        self.assertEqual(safety.exit_reason(m, 95, 125, 115, 110), "target")
        self.assertIsNone(safety.exit_reason({**m, "half_sold": True}, 95, 125, 115, 110))
        self.assertIsNone(safety.exit_reason({**m, "stop": None}, 50, 100, 100, None))


if __name__ == "__main__":
    unittest.main()
