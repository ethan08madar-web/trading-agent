"""Read-only Alpaca access (spec §3.3). Placing orders lives ONLY in paper_orders.py."""
import json
import urllib.request
from datetime import date, timedelta

TRADING_URL = {"paper": "https://paper-api.alpaca.markets", "live": "https://api.alpaca.markets"}
DATA_URL = "https://data.alpaca.markets"


def http_get(url, headers):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return json.load(r)


class Broker:
    def __init__(self, mode, key, secret, get=http_get):
        self.base = TRADING_URL[mode]
        self.h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.get = get

    def clock(self):
        return self.get(self.base + "/v2/clock", self.h)

    def account(self):
        return self.get(self.base + "/v2/account", self.h)

    def positions(self):
        return self.get(self.base + "/v2/positions", self.h)

    def latest_price(self, sym):
        return float(self.get(f"{DATA_URL}/v2/stocks/{sym}/trades/latest?feed=iex", self.h)["trade"]["p"])

    def daily_bars(self, sym, n, before):
        """Last n completed daily bars before the date `before`: [{t, o, h, l, c, v}, ...]."""
        start = (date.fromisoformat(before) - timedelta(days=n * 2 + 10)).isoformat()
        d = self.get(f"{DATA_URL}/v2/stocks/{sym}/bars?timeframe=1Day&start={start}"
                     f"&limit=1000&adjustment=all&feed=iex", self.h)
        return [b for b in (d.get("bars") or []) if b["t"][:10] < before][-n:]

    def daily_closes(self, sym, n, before):
        return [b["c"] for b in self.daily_bars(sym, n, before)]
