"""Spec §3.3: live mode must never reach order code."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN = r'''
import os, sys
from unittest import mock
import robot.main as m

class FB:
    def __init__(self, *a): pass
    def clock(self): return {"is_open": True, "timestamp": "2026-11-09T10:00:00-05:00",
                             "next_close": "2026-11-09T16:00:00-05:00"}
    def account(self): return {"equity": "1000", "cash": "1000"}
    def positions(self): return [{"symbol": "ABC", "qty": "4", "avg_entry_price": "50"}]
    def latest_price(self, s): return 40.0
    def daily_closes(self, s, n, before): return []

os.environ.update(APCA_API_KEY_ID="x", APCA_API_SECRET_KEY="y")
with mock.patch.object(m, "Broker", FB), mock.patch.object(m.telegram, "send", lambda *a: True):
    m.main(["--notebook", sys.argv[1]])
print("LOADED" if "robot.paper_orders" in sys.modules else "CLEAN")
'''
SETTINGS = (ROOT / "notebook" / "settings.yaml").read_text(encoding="utf-8").replace("mode: paper", "mode: live")
PLAN = ('{"date": "2026-11-09", "market_light": "green", "picks": '
        '[{"symbol": "XYZ", "entry_max": 50, "stop": 47.5, "target": 56, "reason": "x"}]}')


class LiveGuardTest(unittest.TestCase):
    def test_only_paper_orders_mentions_orders_endpoint(self):
        for f in (ROOT / "robot").glob("*.py"):
            if f.name != "paper_orders.py":
                self.assertNotIn("v2/orders", f.read_text(encoding="utf-8"), f.name)

    def test_live_run_never_imports_order_code(self):
        nb = pathlib.Path(tempfile.mkdtemp())
        (nb / "plan").mkdir()
        (nb / "settings.yaml").write_text(SETTINGS, encoding="utf-8")
        (nb / "plan" / "2026-11-09.json").write_text(PLAN, encoding="utf-8")
        r = subprocess.run([sys.executable, "-c", RUN, str(nb)], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip().splitlines()[-1], "CLEAN")
        self.assertIn("Alpaca app", (nb / "trades.jsonl").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
