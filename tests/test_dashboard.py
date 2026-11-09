import json
import os
import tempfile
import unittest
from datetime import datetime, timezone

from robot.dashboard import next_update, render, render_markdown


class DashboardTest(unittest.TestCase):
    def test_empty_notebook_renders(self):
        self.assertIn("Mission Control", render(tempfile.mkdtemp()))

    def test_content_shown_and_escaped(self):
        nb = tempfile.mkdtemp()
        os.makedirs(os.path.join(nb, "plan"))
        with open(os.path.join(nb, "plan", "2026-11-09.json"), "w", encoding="utf-8") as f:
            json.dump({"market_light": "green", "fmp_calls": 42, "picks": [
                {"symbol": "ABC", "entry_max": 50, "stop": 47.5, "target": 56, "reason": "<b>x</b>"}]}, f)
        with open(os.path.join(nb, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"positions": {"XYZ": {"entry": 10, "stop": 9, "target": 12, "sleeve": False}},
                       "paused": True, "pause_reason": "3 losing trades in a row", "last_check": "t"}, f)
        page = render(nb)
        for text in ("ABC", "XYZ", "🟢", "42", "3 losing trades in a row", "&lt;b&gt;x&lt;/b&gt;"):
            self.assertIn(text, page)
        self.assertNotIn("<b>x</b>", page)
        self.assertIn("XYZ", render_markdown(nb))

    def test_portfolio_value_and_week_change(self):
        nb = tempfile.mkdtemp()
        with open(os.path.join(nb, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"week_start_equity": 1000, "equity_history": [["2026-11-09T10:00", 1000],
                       ["bad"], ["2026-11-09T10:15", "x"], ["2026-11-09T10:30", 1012.5]]}, f)
        page = render(nb)
        self.assertIn("$1,012.50", page)
        self.assertIn("▲ +$12.50 (+1.25%)", page)
        self.assertIn('class="chg up"', page)

    def test_detail_numbers(self):
        nb = tempfile.mkdtemp()
        os.makedirs(os.path.join(nb, "plan"))
        with open(os.path.join(nb, "plan", "2026-11-09.json"), "w", encoding="utf-8") as f:
            json.dump({"picks": [{"symbol": "ABC", "entry_max": 50, "stop": 47.5, "target": 56}]}, f)
        with open(os.path.join(nb, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"positions": {"XYZ": {"entry": 10, "stop": 9, "target": 12}}, "last_prices": {"XYZ": 11},
                       "loss_streak": 2, "pending": {"QQQ": {}}}, f)
        page = render(nb)
        for text in ("risks 5.0% to the stop", "reward 2.4× the risk", "▲ +10.00%", "18.2% above stop",
                     "+9.1% to target", "width:67%", "2 of 3", "QQQ", 'data-theme="dark"'):
            self.assertIn(text, page)

    def test_next_update(self):
        utc = lambda *a: datetime(*a, tzinfo=timezone.utc)
        cases = [(utc(2026, 11, 9, 13, 0), "2026-11-09 09:00"),   # Mon before plan
                 (utc(2026, 11, 9, 14, 5), "2026-11-09 12:30"),   # just after plan → adjust
                 (utc(2026, 11, 13, 22, 0), "2026-11-14 10:00"),  # Fri after report → Sat weekly
                 (utc(2026, 11, 14, 15, 30), "2026-11-16 09:00")]  # Sat after weekly → Mon plan
        for now, want in cases:
            self.assertEqual(next_update(now).strftime("%Y-%m-%d %H:%M"), want)
        self.assertIn("Next update:", render(tempfile.mkdtemp()))

    def test_torn_trades_line_keeps_other_lines(self):
        nb = tempfile.mkdtemp()
        with open(os.path.join(nb, "trades.jsonl"), "w", encoding="utf-8") as f:
            f.write('{"time": "t1", "text": "GOODONE"}\n{"time": "x", "te\n{"time": "t2", "text": "GOODTWO"}\n')
        page = render(nb)
        self.assertIn("GOODONE", page)
        self.assertIn("GOODTWO", page)
        self.assertIn("GOODTWO", render_markdown(nb))

    def test_malformed_plan_and_state_do_not_crash(self):
        nb = tempfile.mkdtemp()
        os.makedirs(os.path.join(nb, "plan"))
        with open(os.path.join(nb, "plan", "2026-11-09.json"), "w", encoding="utf-8") as f:
            json.dump([1, 2], f)
        with open(os.path.join(nb, "state.json"), "w", encoding="utf-8") as f:
            json.dump({"positions": {"A": "oops"}, "last_prices": []}, f)
        self.assertIn("Mission Control", render(nb))
        self.assertIn("Mission Control", render_markdown(nb))


if __name__ == "__main__":
    unittest.main()
