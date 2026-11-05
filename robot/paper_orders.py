"""The ONLY code that can place orders (spec §3.3). Paper account only: the URL is
hardcoded here on purpose and is never a setting. main.py imports this file only when
mode == paper; tests/test_live_guard.py fails if live mode can reach it."""
import json
import urllib.request

PAPER_URL = "https://paper-api.alpaca.markets"


def http_send(method, url, headers, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={**headers, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


class PaperOrders:
    def __init__(self, key, secret, send=http_send):
        self.h = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
        self.send = send

    def _order(self, body):
        return self.send("POST", PAPER_URL + "/v2/orders", self.h, body)

    def open_orders(self):
        return self.send("GET", PAPER_URL + "/v2/orders?status=open&limit=500", self.h)

    def buy_limit(self, sym, qty, limit):
        return self._order({"symbol": sym, "qty": str(qty), "side": "buy", "type": "limit",
                            "limit_price": f"{limit:.2f}", "time_in_force": "day"})

    def sell_market(self, sym, qty):
        return self._order({"symbol": sym, "qty": str(qty), "side": "sell", "type": "market",
                            "time_in_force": "day"})

    def place_stop(self, sym, qty, stop):
        """Whole shares only: Alpaca doesn't accept stop orders for fractional shares."""
        return self._order({"symbol": sym, "qty": str(qty), "side": "sell", "type": "stop",
                            "stop_price": f"{stop:.2f}", "time_in_force": "gtc"})

    def cancel_for(self, sym):
        for o in self.open_orders():
            if o["symbol"] == sym:
                self.send("DELETE", f"{PAPER_URL}/v2/orders/{o['id']}", self.h)
