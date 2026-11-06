"""Checks for Claude's plan run: bad data, earnings soon, and price levels for each candidate.
Read-only (prices from Alpaca, earnings from FMP). The Robot never imports this.

    python -m robot.research AAPL MSFT NVDA

One line per symbol: DROP <why>, or KEEP with the facts Claude needs to set entry, stop, target.
Uses 1 FMP call in total, whatever the number of symbols."""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from robot.broker import Broker
from robot.safety import floor2

FMP_EARNINGS = "https://financialmodelingprep.com/stable/earnings-calendar"
EARNINGS_DAYS = 3      # don't buy with earnings within 3 trading days (spec §4)
MIN_BARS = 50          # enough history for the 50-day average
MAX_GAP = 0.10         # latest price this far from the last close = data we don't trust
MAX_STOP = 0.15        # stop more than 15% below entry is refused by the Robot


def window_end(today, trading_days=EARNINGS_DAYS):
    """Date `trading_days` weekdays after today.
    ponytail: weekdays, not the exchange calendar; a holiday makes the window one day longer (safer)."""
    d, left = today, trading_days
    while left:
        d += timedelta(days=1)
        if d.weekday() < 5:
            left -= 1
    return d


def earnings_soon(rows, symbols, today):
    """{symbol: report date} for symbols reporting from today to window_end(today), any company size."""
    end, want, out = window_end(today), set(symbols), {}
    for r in rows or []:
        sym, d = r.get("symbol"), r.get("date")
        if sym in want and d and today.isoformat() <= d[:10] <= end.isoformat():
            out[sym] = min(out.get(sym, d[:10]), d[:10])
    return out


def data_problem(price, bars, today):
    """Why this symbol's data can't be trusted, or None."""
    if not price or price <= 0:
        return "no usable latest price"
    if len(bars) < MIN_BARS:
        return f"only {len(bars)} days of price history"
    if any(not b.get(k) or b[k] <= 0 for b in bars for k in ("h", "l", "c")):
        return "a daily bar has a zero or missing price"
    last = date.fromisoformat(bars[-1]["t"][:10])
    if (today - last).days > 5:
        return f"price history stops at {last}"
    gap = price / bars[-1]["c"] - 1
    if abs(gap) > MAX_GAP:
        return f"latest ${price:.2f} is {gap:+.0%} from last close ${bars[-1]['c']:.2f}"
    return None


def levels(price, bars):
    """Facts for setting entry/stop/target, plus a mechanical default Claude may tighten."""
    closes = [b["c"] for b in bars]
    low10 = min(b["l"] for b in bars[-10:])
    entry = round(max(price, closes[-1]) * 1.01, 2)
    stop = floor2(low10 * 0.99)
    out = {"last": closes[-1], "sma20": sum(closes[-20:]) / 20, "sma50": sum(closes[-50:]) / 50,
           "low10": low10, "high20": max(b["h"] for b in bars[-20:]),
           "entry_max": entry, "stop": stop, "target": round(entry + 2 * (entry - stop), 2)}
    out["stop_ok"] = entry * (1 - MAX_STOP) <= stop < entry
    return out


def check(symbols, broker, earnings_rows, today):
    """One result line per symbol. earnings_rows=None means FMP couldn't be read."""
    soon = earnings_soon(earnings_rows, symbols, today) if earnings_rows is not None else {}
    lines = []
    for sym in symbols:
        if earnings_rows is None:
            lines.append(f"DROP {sym}: earnings date unknown (FMP not reachable)")
            continue
        if sym in soon:
            lines.append(f"DROP {sym}: earnings {soon[sym]}")
            continue
        try:
            price = broker.latest_price(sym)
            bars = broker.daily_bars(sym, 60, today.isoformat())
        except Exception as e:  # no exception text: it can contain URLs
            lines.append(f"DROP {sym}: price data not reachable ({type(e).__name__})")
            continue
        why = data_problem(price, bars, today)
        if why:
            lines.append(f"DROP {sym}: {why}")
            continue
        v = levels(price, bars)
        note = "" if v["stop_ok"] else "  (default stop is over 15% below: needs a closer stop or DROP)"
        lines.append(f"KEEP {sym}: last ${v['last']:.2f} · 20d avg ${v['sma20']:.2f} · 50d avg ${v['sma50']:.2f}"
                     f" · 10d low ${v['low10']:.2f} · 20d high ${v['high20']:.2f}"
                     f" · default entry_max {v['entry_max']:.2f} stop {v['stop']:.2f}"
                     f" target {v['target']:.2f}{note}")
    return lines


def fetch_earnings(key, today):
    if not key:
        return None
    url = (f"{FMP_EARNINGS}?from={today.isoformat()}&to={window_end(today).isoformat()}&apikey={key}")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            rows = json.load(r)
        return rows if isinstance(rows, list) else None
    except Exception:
        return None


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    symbols = [s.upper() for s in (argv if argv is not None else sys.argv[1:])]
    if not symbols:
        print("usage: python -m robot.research SYMBOL [SYMBOL ...]")
        return 2
    env = os.environ
    today = datetime.now(ZoneInfo("America/New_York")).date()
    broker = Broker("paper", env["APCA_API_KEY_ID"], env["APCA_API_SECRET_KEY"])  # data calls only
    for line in check(symbols, broker, fetch_earnings(env.get("FMP_API_KEY"), today), today):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
