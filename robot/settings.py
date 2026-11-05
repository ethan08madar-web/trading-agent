"""Load and check notebook/settings.yaml (spec §4).

The ceilings are Ethan's "Careful" limits: settings can make them stricter, never looser.
Loosening one is a code change on purpose, not a typo in a YAML file."""
import yaml

FLOATS = {"risk_per_trade": 0.01, "max_position": 0.30,
          "max_stop_distance": 0.25, "week_loss_limit": 0.05}
INTS = {"max_positions": (1, 4), "loss_streak_limit": (1, 3), "breaker_reset": (0, 10**6)}


def load_settings(path):
    with open(path, encoding="utf-8") as f:
        s = yaml.safe_load(f) or {}
    if s.get("mode") not in ("paper", "live"):
        raise ValueError("settings: mode must be paper or live")
    if not isinstance(s.get("sleeve_symbol"), str):
        raise ValueError("settings: sleeve_symbol must be a ticker")
    for k, ceiling in FLOATS.items():
        v = s.get(k)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v <= ceiling:
            raise ValueError(f"settings: {k} must be a number above 0 and at most {ceiling}")
        s[k] = float(v)
    for k, (lo, hi) in INTS.items():
        v = s.get(k)
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ValueError(f"settings: {k} must be a whole number from {lo} to {hi}")
    return s
