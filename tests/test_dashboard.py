import json
import os
import tempfile
import unittest

from robot.dashboard import render, render_markdown


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


if __name__ == "__main__":
    unittest.main()
