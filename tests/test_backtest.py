import unittest

from backtest import data


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
