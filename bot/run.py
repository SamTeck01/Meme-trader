"""Main loop (paper mode).

Lanes: B (pump.fun curve, live websocket), C (trending momentum), D (hype/conviction).
Lane A (smart wallets) and the AI judge plug in later.
Usage: python -m bot.run [--cycles N] [--interval SECONDS]
"""
import argparse
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import CONFIG, SOL_MINT
from .data import dexscreener
from . import aroon, momentum, safety
from .data import geckoterminal
from .lanes import hype
from .lanes.pumpfun import PumpLane
from .paper import PaperBroker
from .risk import DayState, RiskManager, today

MIN_MOMENTUM = 60
CONVICTION_HYPE = 70
CONVICTION_MIN_MOMENTUM = 45
MAX_CHECKS_PER_CYCLE = 15


@dataclass
class Candidate:
    mint: str
    lane: str
    on_curve: bool = False
    curve_price_sol: float = 0.0
    hype_info: dict = field(default_factory=dict)
    note: str = ""


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%H:%M:%S} {msg}", flush=True)


def sol_usd() -> float:
    p = dexscreener.best_pair(SOL_MINT)
    return float(p["priceUsd"]) if p and p.get("priceUsd") else 0.0


def price_of(mint: str) -> float | None:
    p = dexscreener.best_pair(mint)
    return float(p["priceUsd"]) if p and p.get("priceUsd") else None


def manage_exits(broker: PaperBroker, rm: RiskManager, day: DayState) -> dict[str, float]:
    prices = {}
    for mint, p in list(broker.positions.items()):
        price = price_of(mint)
        if price is None:
            continue
        prices[mint] = price
        act = rm.check_exit(p, price, datetime.now(timezone.utc))
        if act:
            got = broker.sell(mint, act.fraction, price, act.reason)
            day.fees_spent += broker.fee_usd
            log(f"SELL {p.symbol} {act.fraction:.0%} @ {price:.8g} ({act.reason}) ${got:.2f}")
            if mint not in broker.positions:
                pnl = broker.realized_pnl(mint)
                rm.record_close(p, pnl, day)
                log(f"CLOSED {p.symbol} [{p.lane}] P&L ${pnl:+.2f}")
    return prices


def gather_candidates(pump: PumpLane) -> list[Candidate]:
    out = [Candidate(t.mint, "B", on_curve=True, curve_price_sol=t.price_sol,
                     note=f"curve {t.progress:.0%}, {len(t.buyers)} buyers") for t in pump.candidates()]
    for mint, info in hype.collect().items():
        out.append(Candidate(mint, "CD", hype_info=info))
    return out


def decide(c: Candidate, inp: safety.SafetyInputs) -> tuple[bool, bool, str, str]:
    """Returns (buy, conviction, symbol, reason). AI judge will be added here."""
    sym = ((inp.pair or {}).get("baseToken") or {}).get("symbol") or "?"
    if c.lane == "B":
        res = safety.evaluate(inp, on_curve=True)
        return res.passed, False, sym, res.summary() if not res.passed else c.note
    mom, mnotes = momentum.score(inp.pair or {})
    hs, hnotes = hype.hype_score(c.hype_info, sym, c.mint)
    # Aroon only when it could change the outcome (saves the 30/min candle limit)
    if mom >= CONVICTION_MIN_MOMENTUM - 15 and inp.pair and inp.pair.get("pairAddress"):
        try:
            cs = geckoterminal.candles(inp.pair["pairAddress"])
        except Exception:
            cs = []
        mom, anote, blocked = aroon.adjust(mom, cs)
        mnotes.append(anote)
        if blocked:
            return False, False, sym, f"{anote}; momentum {mom}"
    conviction = hs >= CONVICTION_HYPE and mom >= CONVICTION_MIN_MOMENTUM
    res = safety.evaluate(inp, conviction=conviction)
    if not res.passed:
        return False, False, sym, res.summary()
    if conviction:
        return True, True, sym, f"HYPE {hs} ({', '.join(hnotes)}) momentum {mom}"
    if mom >= MIN_MOMENTUM:
        return True, False, sym, f"momentum {mom} ({', '.join(mnotes)})"
    return False, False, sym, f"momentum {mom}, hype {hs}"


def look_for_entries(broker, rm, day, prices, pump, seen: dict) -> None:
    cands = gather_candidates(pump)
    checked = 0
    for c in cands:
        if c.mint in broker.positions or time.time() - seen.get(c.mint, 0) < 15 * 60:
            continue
        if checked >= MAX_CHECKS_PER_CYCLE:
            break
        eq = broker.equity(prices)
        ok, why = rm.can_open(broker.cash, eq, list(broker.positions.values()), day, conviction=False)
        if not ok:
            log(f"no entries: {why}")
            return
        checked += 1
        seen[c.mint] = time.time()
        inp = safety.gather(c.mint)
        buy, conviction, sym, reason = decide(c, inp)
        if not buy:
            log(f"skip {sym} [{c.lane}]: {reason[:120]}")
            continue
        if conviction:
            ok, why = rm.can_open(broker.cash, eq, list(broker.positions.values()), day, conviction=True)
            if not ok:
                log(f"skip {sym} conviction: {why}")
                continue
        if inp.pair and inp.pair.get("priceUsd"):
            price = float(inp.pair["priceUsd"])
        else:
            price = c.curve_price_sol * sol_usd()
        if price <= 0:
            continue
        lane = "D" if conviction else ("B" if c.lane == "B" else "C")
        size = rm.size_usd(eq, broker.cash, conviction)
        broker.buy(c.mint, sym, size, price, lane=lane, conviction=conviction)
        day.fees_spent += broker.fee_usd
        log(f"BUY {sym} [{lane}] ${size:.2f} @ {price:.8g} — {reason}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=0, help="0 = run forever")
    ap.add_argument("--interval", type=int, default=60)
    a = ap.parse_args()
    if not CONFIG.paper_mode:
        raise SystemExit("Live mode is not implemented yet. Paper only.")
    broker, rm = PaperBroker(), RiskManager()
    pump = PumpLane()
    pump.start()
    day = DayState(today(), broker.equity({}))
    seen: dict[str, float] = {}
    n = 0
    while True:
        if day.day != today():
            day = DayState(today(), broker.equity({}))
        prices = manage_exits(broker, rm, day)
        pump.poll(sol_usd())
        look_for_entries(broker, rm, day, prices, pump, seen)
        eq = broker.equity(prices)
        log(f"equity ${eq:.2f} cash ${broker.cash:.2f} open {len(broker.positions)} "
            f"fees ${broker.fees_total:.2f} | pump: {pump.stats}")
        n += 1
        if a.cycles and n >= a.cycles:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
