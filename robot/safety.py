"""Pure safety maths (spec §4). No network, no files: everything here is unit-tested."""
import math


def floor2(x):
    return math.floor(round(x * 100, 6)) / 100


def round_qty(qty):
    """Whole shares when >= 1 (so a broker stop order can be placed), else 0.01 fractions."""
    return math.floor(qty) if qty >= 1 else floor2(qty)


def position_size(equity, cash, entry, stop, s):
    """Shares to buy: lose at most risk_per_trade if the stop hits, at most max_position
    of the account, and no more than the cash. 0 means don't buy."""
    if entry <= 0 or stop <= 0 or stop >= entry or stop < entry * (1 - s["max_stop_distance"]):
        return 0
    qty = min(s["risk_per_trade"] * equity / (entry - stop),
              s["max_position"] * equity / entry,
              max(cash, 0) / entry)
    return round_qty(qty)


def max_positions_for(light, falling, s):
    if light == "green":
        return s["max_positions"]
    if light == "yellow" and not falling:
        return min(2, s["max_positions"])
    return 0


def breaker_reason(equity, week_start_equity, loss_streak, s):
    if week_start_equity:
        change = equity / week_start_equity - 1
        if change <= -s["week_loss_limit"]:
            return f"account down {abs(change):.1%} this week"
    if loss_streak >= s["loss_streak_limit"]:
        return f"{loss_streak} losing trades in a row"
    return None


def is_loss(entry, exit_price):
    return exit_price < entry * 0.995  # stop moved to entry exits near 0: not a loss


def sma(values, n):
    return sum(values[-n:]) / n if len(values) >= n else None
