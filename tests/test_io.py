import unittest
from unittest import mock

from robot import paper_orders, telegram
from robot.broker import Broker


class BrokerTest(unittest.TestCase):
    def test_urls_by_mode_and_parsing(self):
        seen = []

        def get(url, headers):
            seen.append(url)
            if "/trades/latest" in url:
                return {"trade": {"p": 101.5}}
            if "/bars" in url:
                return {"bars": [{"t": "2026-11-05T05:00:00Z", "c": 1}, {"t": "2026-11-06T05:00:00Z", "c": 2},
                                 {"t": "2026-11-09T05:00:00Z", "c": 99}]}  # today's partial bar
            return {}

        b = Broker("paper", "k", "s", get=get)
        b.clock()
        self.assertTrue(seen[-1].startswith("https://paper-api.alpaca.markets/v2/clock"))
        Broker("live", "k", "s", get=get).account()
        self.assertTrue(seen[-1].startswith("https://api.alpaca.markets/v2/account"))
        self.assertEqual(b.latest_price("AAPL"), 101.5)
        self.assertEqual(b.daily_closes("AAPL", 5, "2026-11-09"), [1, 2])

    def test_bad_mode(self):
        with self.assertRaises(KeyError):
            Broker("real", "k", "s")


class PaperOrdersTest(unittest.TestCase):
    def test_paper_url_and_bodies(self):
        self.assertEqual(paper_orders.PAPER_URL, "https://paper-api.alpaca.markets")
        calls = []

        def send(method, url, headers, body=None):
            calls.append((method, url, body))
            if method == "GET":
                return [{"id": "1", "symbol": "AAPL"}, {"id": "2", "symbol": "MSFT"}]

        o = paper_orders.PaperOrders("k", "s", send=send)
        o.buy_limit("AAPL", 1, 231.5)
        self.assertEqual(calls[-1][2], {"symbol": "AAPL", "qty": "1", "side": "buy", "type": "limit",
                                        "limit_price": "231.50", "time_in_force": "day"})
        o.place_stop("AAPL", 2, 224)
        self.assertEqual(calls[-1][2]["time_in_force"], "gtc")
        o.cancel_for("AAPL")
        self.assertEqual(calls[-1][:2], ("DELETE", "https://paper-api.alpaca.markets/v2/orders/1"))
        self.assertTrue(all(c[1].startswith(paper_orders.PAPER_URL) for c in calls))


class TelegramTest(unittest.TestCase):
    def test_never_raises(self):
        self.assertFalse(telegram.send("", "", "hi"))
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertFalse(telegram.send("t", "c", "hi"))

    def test_card_bolds_and_escapes(self):
        c = telegram.card("📋 Plan <ready>", ["**2 picks:** A&B", "", "x < y"], "Paper money")
        self.assertEqual(c, "<b>📋 Plan &lt;ready&gt;</b>\n\n<b>2 picks:</b> A&amp;B\n\nx &lt; y\n\n<i>Paper money</i>")

    def test_html_mode_sets_parse_mode(self):
        sent = {}
        with mock.patch("urllib.request.urlopen", lambda url, data, timeout: sent.update(d=data)):
            self.assertTrue(telegram.send("t", "c", "<b>x</b>", True))
        self.assertIn(b"parse_mode=HTML", sent["d"])


if __name__ == "__main__":
    unittest.main()
