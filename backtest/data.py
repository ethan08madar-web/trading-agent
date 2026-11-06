"""Free price history for the scoreboard: Yahoo daily bars (no key needed) and the past
S&P 500 member list (github.com/fja05680/sp500, MIT). Downloads are cached in backtest/cache/."""
import bisect
import csv
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

MEMBERS_URL = ("https://raw.githubusercontent.com/fja05680/sp500/master/"
               "S%26P%20500%20Historical%20Components%20%26%20Changes%20(Updated).csv")
YAHOO = "https://query1.finance.yahoo.com/v8/finance/chart/{}?period1={}&period2={}&interval=1d&events=div%2Csplits"
CACHE = os.path.join(os.path.dirname(__file__), "cache")
START = "2018-01-01"  # a year before 2019, so 200-day averages and 12-month strength exist


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (trading-agent backtest)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def load_members(text):
    """[(date, {tickers})] oldest first, rows from START on."""
    rows = []
    for r in list(csv.reader(text.splitlines()))[1:]:
        if len(r) == 2 and r[0] >= START:
            rows.append((r[0], set(r[1].split(","))))
    return rows


def members_on(rows, day):
    """Tickers in the index on `day`: the latest row dated on or before it."""
    i = bisect.bisect_right([d for d, _ in rows], day) - 1
    return rows[i][1] if i >= 0 else set()


def yahoo_bars(payload):
    """Yahoo chart JSON -> [{t, o, h, l, c, v}] adjusted for splits and dividends; bad rows dropped."""
    res = payload["chart"]["result"][0]
    q, adj = res["indicators"]["quote"][0], res["indicators"]["adjclose"][0]["adjclose"]
    out = []
    for i, ts in enumerate(res.get("timestamp") or []):
        o, h, l, c, v, a = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i], adj[i]
        if None in (o, h, l, c, a) or c <= 0 or a <= 0:
            continue
        f = a / c
        out.append({"t": datetime.fromtimestamp(ts, timezone.utc).date().isoformat(),
                    "o": o * f, "h": h * f, "l": l * f, "c": a, "v": v or 0})
    return out


def _cached(name, fetch, refresh):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if os.path.exists(path) and not refresh:
        with open(path, encoding="utf-8") as f:
            return f.read()
    text = fetch()
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def members(refresh=False):
    return load_members(_cached("members.csv", lambda: _get(MEMBERS_URL).decode("utf-8"), refresh))


def bars(sym, refresh=False):
    """Cached daily bars for sym from START, or [] if Yahoo has none (most companies that stopped trading)."""
    def fetch():
        p1 = int(datetime.fromisoformat(START).replace(tzinfo=timezone.utc).timestamp())
        url = YAHOO.format(sym.replace(".", "-"), p1, int(time.time()))
        time.sleep(0.3)  # be polite to a free service
        try:
            return json.dumps(yahoo_bars(json.loads(_get(url))))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "[]"
            raise  # anything else (rate limit, outage) must not be cached as "no data"
    return json.loads(_cached(f"{sym}.json", fetch, refresh))
