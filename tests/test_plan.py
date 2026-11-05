import json
import os
import subprocess
import sys
import tempfile
import unittest

from robot.plan import load_plan, validate_plan

TODAY = "2026-11-09"
GOOD = {"date": TODAY, "version": 1, "market_light": "green",
        "picks": [{"symbol": "AAPL", "entry_max": 231.5, "stop": 224.0, "target": 246.0, "reason": "x"}]}


def write(obj):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(obj if isinstance(obj, str) else json.dumps(obj))
    return path


class PlanTest(unittest.TestCase):
    def test_good_plan_gets_defaults(self):
        plan, errs = load_plan(write(GOOD), TODAY)
        self.assertEqual(errs, [])
        self.assertEqual(plan["stops"], {})
        self.assertEqual(plan["trend_sleeve"], {"hold_spy": False})
        self.assertFalse(plan["light_falling"])

    def test_missing_file_and_bad_json(self):
        self.assertIsNone(load_plan("no/such/file.json", TODAY)[0])
        self.assertIsNone(load_plan(write("{not json"), TODAY)[0])

    def test_problems(self):
        cases = {
            "old date": {**GOOD, "date": "2026-11-06"},
            "bad light": {**GOOD, "market_light": "blue"},
            "stop above entry": {**GOOD, "picks": [{**GOOD["picks"][0], "stop": 240.0}]},
            "bad symbol": {**GOOD, "picks": [{**GOOD["picks"][0], "symbol": "aapl;rm"}]},
            "trailing newline": {**GOOD, "picks": [{**GOOD["picks"][0], "symbol": "AAPL\n"}]},
            "newline in cancel": {**GOOD, "cancel": ["AAPL\n"]},
            "bool price": {**GOOD, "picks": [{**GOOD["picks"][0], "target": True}]},
            "bad stops": {**GOOD, "stops": {"AAPL": "high"}},
            "bad sleeve": {**GOOD, "trend_sleeve": {"hold_spy": "yes"}},
        }
        for name, p in cases.items():
            with self.subTest(name):
                self.assertNotEqual(validate_plan(p, TODAY), [])

    def test_cli(self):
        ok = subprocess.run([sys.executable, "-m", "robot.plan", write(GOOD), TODAY], capture_output=True, text=True)
        bad = subprocess.run([sys.executable, "-m", "robot.plan", write({}), TODAY], capture_output=True, text=True)
        self.assertEqual((ok.returncode, ok.stdout.strip()), (0, "OK"))
        self.assertEqual(bad.returncode, 1)


if __name__ == "__main__":
    unittest.main()
