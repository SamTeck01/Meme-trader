"""Shadow tracker: the bot's evidence engine (STRATEGY.md §3).

Every token that passes the HARD safety checks is followed forward for 6 hours whether
or not we bought it. For each one we store the signal features, the price at fixed
horizons, and what our real exit rules would have returned. That gives hundreds of
observations a day instead of a handful of trades, so we can see which lanes and filters
actually have an edge. Costs nothing: one batched DexScreener call per 30 tokens.
"""
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .data import dexscreener
from .risk import Position, RiskManager

ACTIVE = Path("data/shadow_active.json")
DONE = Path("data/shadow.jsonl")
HORIZONS = {"r5m": 300, "r15m": 900, "r1h": 3600, "r6h": 21600}
WINDOW_S = 21600
MAX_ACTIVE = 300
RUG_LIQ_USD = 500.0       # liquidity gone = rug, position worth ~0
RUG_MIN_START_LIQ = 2000.0
RUG_MISSES = 5            # price unavailable this many polls in a row = rug


@dataclass
class Obs:
    mint: str
    symbol: str
    lane: str
    t0: float
    p0: float
    features: dict
    bought: bool = False
    hi: float = 1.0
    lo: float = 1.0
    last: float = 1.0
    misses: int = 0
    marks: dict = field(default_factory=dict)
    # simulated position under the real exit rules (gross, no costs)
    sim_left: float = 1.0          # fraction of tokens still held
    sim_out: float = 0.0           # proceeds so far, as multiple of cost
    sim_peak: float = 0.0
    tp1: bool = False
    tp2: bool = False
    sim_reason: str = ""


class Shadow:
    def __init__(self, active: Path = ACTIVE, done: Path = DONE, rm: RiskManager | None = None):
        self.active_file, self.done_file = active, done
        self.rm = rm or RiskManager()
        self.obs: dict[str, Obs] = {}
        if active.exists():
            try:
                self.obs = {m: Obs(**o) for m, o in json.loads(active.read_text()).items()}
            except (ValueError, TypeError):
                self.obs = {}

    def observe(self, mint: str, symbol: str, lane: str, price: float, features: dict,
                bought: bool = False, now: float | None = None) -> None:
        if price <= 0 or len(self.obs) >= MAX_ACTIVE:
            return
        if mint in self.obs:
            self.obs[mint].bought = self.obs[mint].bought or bought
            return
        self.obs[mint] = Obs(mint, symbol, lane, time.time() if now is None else now, price, features, bought, sim_peak=price)

    # ---------- per-observation update ----------
    def _sim(self, o: Obs, price: float, now: float) -> None:
        if o.sim_left <= 0:
            return
        p = Position(mint=o.mint, symbol=o.symbol, lane=o.lane, conviction=o.lane == "D",
                     entry_price=o.p0, tokens=o.sim_left, initial_tokens=1.0, cost_usd=1.0,
                     opened_at=datetime.fromtimestamp(o.t0, timezone.utc), peak_price=o.sim_peak,
                     tp1_done=o.tp1, tp2_done=o.tp2)
        act = self.rm.check_exit(p, price, datetime.fromtimestamp(now, timezone.utc))
        o.sim_peak, o.tp1, o.tp2 = p.peak_price, p.tp1_done, p.tp2_done
        if act:
            sold = o.sim_left * act.fraction
            o.sim_out += sold * price / o.p0
            o.sim_left -= sold
            if o.sim_left <= 1e-9:
                o.sim_left, o.sim_reason = 0.0, act.reason

    def update_one(self, o: Obs, price: float | None, liq: float | None, now: float) -> bool:
        """Returns True when the observation is finished."""
        rug = False
        if price is None or price <= 0:
            o.misses += 1
            rug = o.misses >= RUG_MISSES
        else:
            o.misses = 0
            # only meaningful if we saw real liquidity at the start (curve pairs report $0)
            liq0 = float(o.features.get("liquidity_usd") or 0)
            rug = liq0 >= RUG_MIN_START_LIQ and liq is not None and liq < max(RUG_LIQ_USD, liq0 * 0.1)
        if rug:
            price = 0.0
        if price is not None and (price > 0 or rug):
            m = price / o.p0
            o.last, o.hi, o.lo = m, max(o.hi, m), min(o.lo, m)
            self._sim(o, price, now)
        age = now - o.t0
        for k, s in HORIZONS.items():
            if k not in o.marks and (age >= s or rug):
                o.marks[k] = round(o.last, 4)
        if rug or age >= WINDOW_S:
            if o.sim_left > 0:                       # still holding at window end: mark to market
                o.sim_out += o.sim_left * o.last
                o.sim_left, o.sim_reason = 0.0, "rug" if rug else "open at 6h"
            if rug:
                o.sim_reason = "rug"
            return True
        return False

    def poll(self, now: float | None = None) -> int:
        """Refresh prices for all active observations. Returns how many finished."""
        now = now or time.time()
        mints, finished = list(self.obs), 0
        for i in range(0, len(mints), 30):
            chunk = mints[i:i + 30]
            try:
                pairs = dexscreener.pairs_for(chunk)
            except Exception:
                continue
            best: dict[str, dict] = {}
            for p in pairs:
                m = (p.get("baseToken") or {}).get("address")
                liq = (p.get("liquidity") or {}).get("usd") or 0
                if m and liq >= ((best.get(m) or {}).get("liquidity") or {}).get("usd", -1):
                    best[m] = {**p, "liquidity": {"usd": liq}}
            for m in chunk:
                o, p = self.obs[m], best.get(m)
                price = float(p["priceUsd"]) if p and p.get("priceUsd") else None
                if self.update_one(o, price, p["liquidity"]["usd"] if p else None, now):
                    self._finish(o, now)
                    finished += 1
        self.save()
        return finished

    def _finish(self, o: Obs, now: float) -> None:
        self.done_file.parent.mkdir(parents=True, exist_ok=True)
        rec = {"ts": datetime.fromtimestamp(o.t0, timezone.utc).isoformat(), "mint": o.mint,
               "symbol": o.symbol, "lane": o.lane, "bought": o.bought, "p0": o.p0,
               "hi": round(o.hi, 4), "lo": round(o.lo, 4), **o.marks,
               "sim": round(o.sim_out, 4), "sim_reason": o.sim_reason,
               "rug": o.sim_reason == "rug" or o.last <= 0.1, "features": o.features}
        with self.done_file.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        del self.obs[o.mint]

    def save(self) -> None:
        self.active_file.parent.mkdir(parents=True, exist_ok=True)
        self.active_file.write_text(json.dumps({m: o.__dict__ for m, o in self.obs.items()}, default=str))
