"""Lane B: early pump.fun tokens.

Free mode (default): PumpPortal's free websocket announces every new token; the main loop
calls `poll()` each cycle, which batch-checks tracked tokens on DexScreener (30 per request)
to get curve progress (from market cap) and buy/sell activity.
Paid mode: if PUMPPORTAL_API_KEY is set (key funded with >=0.02 SOL), live per-trade data is
used instead (unique buyers, dev-sell detection).
"""
import math
import os
import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field

import websockets

from ..data import dexscreener

WS_URL = "wss://pumpportal.fun/api/data"
API_KEY = os.getenv("PUMPPORTAL_API_KEY", "")
K_CURVE = START_VSOL_K = 30.0 * 1_073_000_000   # constant product of a fresh curve
MIN_AGE_POLL_MIN = 3
START_VSOL = 30.0          # virtual SOL in a fresh curve
GRAD_REAL_SOL = 85.0       # real SOL raised at graduation
MIN_PROGRESS, MAX_PROGRESS = 0.50, 0.70
MIN_UNIQUE_BUYERS = 25
MIN_BUY_RATIO = 1.3        # buy SOL / sell SOL
MAX_AGE_MIN = 60
MAX_TRACKED = 400
DEV_INITIAL_BUY_MAX_SOL = 3.0


@dataclass
class CurveToken:
    mint: str
    symbol: str
    name: str
    creator: str
    created: float
    dev_buy_sol: float
    v_sol: float = START_VSOL
    v_tokens: float = 1_073_000_000
    buyers: set = field(default_factory=set)
    buy_sol: float = 0.0
    sell_sol: float = 0.0
    dev_sold: bool = False
    emitted: bool = False

    @property
    def progress(self) -> float:
        return max(0.0, (self.v_sol - START_VSOL) / GRAD_REAL_SOL)

    @property
    def price_sol(self) -> float:
        return self.v_sol / self.v_tokens if self.v_tokens else 0.0


def is_candidate(t: CurveToken) -> tuple[bool, str]:
    if t.emitted:
        return False, "already emitted"
    if not (MIN_PROGRESS <= t.progress <= MAX_PROGRESS):
        return False, f"progress {t.progress:.0%}"
    if t.dev_sold:
        return False, "dev sold"
    if t.dev_buy_sol > DEV_INITIAL_BUY_MAX_SOL:
        return False, f"dev bought {t.dev_buy_sol:.1f} SOL"
    if len(t.buyers) < MIN_UNIQUE_BUYERS:
        return False, f"only {len(t.buyers)} buyers"
    if t.sell_sol and t.buy_sol / t.sell_sol < MIN_BUY_RATIO:
        return False, "selling pressure"
    return True, "ok"


class PumpLane:
    def __init__(self):
        self.tokens: dict[str, CurveToken] = {}
        self._out: deque[CurveToken] = deque()
        self._lock = threading.Lock()
        self.stats = {"created": 0, "trades": 0, "emitted": 0}

    # ----- public -----
    def start(self) -> None:
        threading.Thread(target=lambda: asyncio.run(self._run()), daemon=True).start()

    def candidates(self) -> list[CurveToken]:
        with self._lock:
            out = list(self._out)
            self._out.clear()
        return out

    # ----- event handling (pure, testable) -----
    def on_message(self, m: dict) -> list[str]:
        """Process one feed message. Returns mints that need a trade subscription."""
        tx = m.get("txType")
        if tx == "create":
            self.stats["created"] += 1
            t = CurveToken(mint=m["mint"], symbol=m.get("symbol", "?"), name=m.get("name", ""),
                           creator=m.get("traderPublicKey", ""), created=time.time(),
                           dev_buy_sol=float(m.get("solAmount") or 0),
                           v_sol=float(m.get("vSolInBondingCurve") or START_VSOL),
                           v_tokens=float(m.get("vTokensInBondingCurve") or 1_073_000_000))
            self.tokens[t.mint] = t
            self._evict()
            return [t.mint]
        if tx in ("buy", "sell"):
            t = self.tokens.get(m.get("mint"))
            if not t:
                return []
            self.stats["trades"] += 1
            sol = float(m.get("solAmount") or 0)
            trader = m.get("traderPublicKey", "")
            if tx == "buy":
                t.buy_sol += sol
                t.buyers.add(trader)
            else:
                t.sell_sol += sol
                if trader == t.creator:
                    t.dev_sold = True
            t.v_sol = float(m.get("vSolInBondingCurve") or t.v_sol)
            t.v_tokens = float(m.get("vTokensInBondingCurve") or t.v_tokens)
            ok, _ = is_candidate(t)
            if ok:
                t.emitted = True
                self.stats["emitted"] += 1
                with self._lock:
                    self._out.append(t)
        return []

    def update_from_pair(self, t: CurveToken, pair: dict, sol_usd: float) -> None:
        """Free mode: estimate curve state from a DexScreener pumpfun pair."""
        mcap_usd = float(pair.get("marketCap") or pair.get("fdv") or 0)
        if mcap_usd > 0 and sol_usd > 0:
            mcap_sol = mcap_usd / sol_usd
            t.v_sol = math.sqrt(mcap_sol * K_CURVE / 1e9)
            t.v_tokens = K_CURVE / t.v_sol
        h1 = (pair.get("txns") or {}).get("h1") or {}
        # Without per-trade data, buy tx count stands in for unique buyers.
        t.buyers = set(range(int(h1.get("buys") or 0)))
        vb = float(((pair.get("volume") or {}).get("h1")) or 0)
        b, sl = int(h1.get("buys") or 0), int(h1.get("sells") or 0)
        t.buy_sol = vb * b / (b + sl) if b + sl else 0.0
        t.sell_sol = vb * sl / (b + sl) if b + sl else 0.0
        ok, _ = is_candidate(t)
        if ok:
            t.emitted = True
            self.stats["emitted"] += 1
            with self._lock:
                self._out.append(t)

    def poll(self, sol_usd: float) -> None:
        """Free mode: batch-refresh tracked tokens older than MIN_AGE_POLL_MIN."""
        if API_KEY:
            return
        now = time.time()
        due = [t for t in list(self.tokens.values())
               if not t.emitted and now - t.created >= MIN_AGE_POLL_MIN * 60]
        for i in range(0, len(due), 30):
            chunk = due[i:i + 30]
            try:
                pairs = dexscreener.token_pairs(",".join(t.mint for t in chunk))
            except Exception:
                continue
            by_mint = {}
            for p in pairs:
                if p.get("dexId") == "pumpfun":
                    by_mint[(p.get("baseToken") or {}).get("address")] = p
            for t in chunk:
                if t.mint in by_mint:
                    self.update_from_pair(t, by_mint[t.mint], sol_usd)
        self.stats["tracked"] = len(self.tokens)
        self._evict()

    def _evict(self) -> None:
        now = time.time()
        for mint in [m for m, t in self.tokens.items() if now - t.created > MAX_AGE_MIN * 60]:
            del self.tokens[mint]
        while len(self.tokens) > MAX_TRACKED:   # drop the least active
            worst = min(self.tokens.values(), key=lambda t: (len(t.buyers), -t.created))
            del self.tokens[worst.mint]

    # ----- websocket loop -----
    async def _run(self) -> None:
        backoff = 1
        while True:
            try:
                url = f"{WS_URL}?api-key={API_KEY}" if API_KEY else WS_URL
                async with websockets.connect(url, ping_interval=20) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    backoff = 1
                    async for raw in ws:
                        new = self.on_message(json.loads(raw))
                        if new and API_KEY:
                            await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": new}))
            except Exception as e:
                print(f"pump lane reconnect ({e})", flush=True)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
