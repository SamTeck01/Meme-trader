"""Edge report + evidence gate (STRATEGY.md §3-4).

Reads finished shadow observations and answers: after costs, which lanes make money?
A lane with enough evidence and a negative result is switched off automatically
(it keeps being shadow-tracked, so it can earn its way back).
"""
import json
import os
import statistics
import time
from pathlib import Path

from .shadow import DONE

COST_PCT = float(os.getenv("ROUND_TRIP_COST_PCT", "10"))   # fees + slippage, both legs, % of position
MIN_SAMPLES = 40          # evidence needed before a lane can be switched off (or trusted)
LOOKBACK_DAYS = 7
_cache: tuple[float, dict] = (0.0, {})


def load(path: Path = DONE, days: float = LOOKBACK_DAYS) -> list[dict]:
    if not path.exists():
        return []
    cutoff = time.time() - days * 86400
    out = []
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        from datetime import datetime
        if datetime.fromisoformat(r["ts"]).timestamp() >= cutoff:
            out.append(r)
    return out


def stats(rows: list[dict], cost_pct: float = COST_PCT) -> dict:
    if not rows:
        return {"n": 0}
    net = [(r["sim"] - 1) * 100 - cost_pct for r in rows]
    return {"n": len(rows), "mean_net": statistics.mean(net), "median_net": statistics.median(net),
            "win_rate": sum(x > 0 for x in net) / len(net) * 100,
            "rug_rate": sum(bool(r.get("rug")) for r in rows) / len(rows) * 100,
            "mean_1h": statistics.mean((r.get("r1h", 1) - 1) * 100 for r in rows),
            "best": max(net), "worst": min(net)}


def by_lane(rows: list[dict]) -> dict[str, dict]:
    lanes = sorted({r["lane"] for r in rows})
    return {l: stats([r for r in rows if r["lane"] == l]) for l in lanes}


def split(rows: list[dict], name: str, fn) -> tuple[dict, dict]:
    """Does a filter add value? Compare rows where fn(features) is true vs false."""
    yes = [r for r in rows if fn(r.get("features") or {})]
    no = [r for r in rows if not fn(r.get("features") or {})]
    return stats(yes), stats(no)


FILTERS = {
    "passed all soft safety checks": lambda f: not f.get("soft_fails"),
    "rules said BUY": lambda f: bool(f.get("rules_buy")),
    "AI said BUY": lambda f: f.get("ai_buy") is True,
    "aroon uptrend": lambda f: (f.get("aroon") or 0) >= 40,
    "momentum >= 60": lambda f: (f.get("momentum") or 0) >= 60,
    "liquidity >= $30k": lambda f: (f.get("liquidity_usd") or 0) >= 30_000,
}


def lane_allowed(lane: str, rows: list[dict] | None = None) -> tuple[bool, str]:
    """Gate: block a lane once it has >= MIN_SAMPLES rule-approved observations with a negative mean."""
    global _cache
    if rows is None:
        if time.time() - _cache[0] > 600:
            _cache = (time.time(), by_lane([r for r in load() if (r.get("features") or {}).get("rules_buy")]))
        s = _cache[1].get(lane, {"n": 0})
    else:
        s = by_lane([r for r in rows if (r.get("features") or {}).get("rules_buy")]).get(lane, {"n": 0})
    if s["n"] >= MIN_SAMPLES and s["mean_net"] < 0:
        return False, f"lane {lane} switched off: {s['mean_net']:+.1f}% avg after costs over {s['n']} signals"
    return True, "ok"


def _fmt(s: dict) -> str:
    if not s.get("n"):
        return "no data"
    return (f"n={s['n']:<4} avg {s['mean_net']:+6.1f}%  median {s['median_net']:+6.1f}%  "
            f"win {s['win_rate']:3.0f}%  rugs {s['rug_rate']:3.0f}%")


def report(rows: list[dict] | None = None) -> str:
    rows = load() if rows is None else rows
    if not rows:
        return "No finished observations yet (each takes up to 6h)."
    out = [f"Edge report — last {LOOKBACK_DAYS}d, {len(rows)} tokens tracked, "
           f"returns after {COST_PCT:.0f}% round-trip cost, using our exit rules",
           f"ALL            {_fmt(stats(rows))}", "", "By lane (rule-approved signals only):"]
    approved = [r for r in rows if (r.get("features") or {}).get("rules_buy")]
    for lane, s in by_lane(approved).items():
        ok, _ = lane_allowed(lane, rows)
        out.append(f"  {lane}  {_fmt(s)}  {'' if ok else '← OFF'}")
    out += ["", "Does each filter help? (yes vs no)"]
    for name, fn in FILTERS.items():
        y, n = split(rows, name, fn)
        out.append(f"  {name}\n    yes: {_fmt(y)}\n    no:  {_fmt(n)}")
    return "\n".join(out)


if __name__ == "__main__":
    print(report())
