import os
import tempfile
import unittest

from robot.settings import load_settings

GOOD = """mode: paper
risk_per_trade: 0.01
max_position: 0.30
max_positions: 4
max_stop_distance: 0.15
week_loss_limit: 0.05
loss_streak_limit: 3
sleeve_symbol: SPY
breaker_reset: 0
"""


def write(text):
    fd, path = tempfile.mkstemp(suffix=".yaml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


class SettingsTest(unittest.TestCase):
    def test_good_file_loads(self):
        s = load_settings(write(GOOD))
        self.assertEqual(s["mode"], "paper")
        self.assertEqual(s["max_positions"], 4)
        self.assertIsInstance(s["max_position"], float)

    def test_repo_settings_file_is_valid(self):
        self.assertEqual(load_settings("notebook/settings.yaml")["mode"], "paper")

    def test_bad_values_rejected(self):
        for old, new in [
            ("mode: paper", "mode: real"),
            ("risk_per_trade: 0.01", "risk_per_trade: 0.02"),   # looser than Careful
            ("max_positions: 4", "max_positions: 5"),
            ("week_loss_limit: 0.05", "week_loss_limit: 0.10"),
            ("max_stop_distance: 0.15", "max_stop_distance: 0.20"),   # spec 4: reject stops over 15%
            ("loss_streak_limit: 3", "loss_streak_limit: true"),
            ("sleeve_symbol: SPY\n", ""),
        ]:
            with self.subTest(new=new):
                with self.assertRaises(ValueError):
                    load_settings(write(GOOD.replace(old, new)))


if __name__ == "__main__":
    unittest.main()
