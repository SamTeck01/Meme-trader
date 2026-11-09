"""Main loop (paper mode). Lane C (trending) + safety + risk + paper broker.

Lanes A/B/D and the AI judge plug in later.
Usage: python -m bot.run [--cycles N] [--interval SECONDS]
"""
import argparse
import time
from datetime import datetime, timezone

from .config import CONFIG
from .data import dexscreener
from . import momentum, safety
from .paper import PaperBroker
from .risk import DayState, RiskManager, today
from .scan import candidates

MIN_MOMENTUM = 60


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%H:%M:%S} {msg}", flush=True)


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
            log(f"SELL {p.symbol} {act.fraction:.0%} @ {price:.8g} ({act.reason}) +${got:.2f}")
            if mint not in broker.positions:
                pnl = broker.realized_pnl(mint)
                rm.record_close(p, pnl, day)
                log(f"CLOSED {p.symbol} P&L ${pnl:+.2f}")
    return prices


def look_for_entries(broker, rm, day, prices) -> None:
    for mint in candidates(20):
        if mint in broker.positions:
            continue
        eq = broker.equity(prices)
        ok, why = rm.can_open(broker.cash, eq, list(broker.positions.values()), day, conviction=False)
        if not ok:
            log(f"no entries: {why}")
            return
        inp = safety.gather(mint)
        res = safety.evaluate(inp)
        if not res.passed or not inp.pair:
            continue
        sc, notes = momentum.score(inp.pair)
        sym = (inp.pair.get("baseToken") or {}).get("symbol", "?")
        if sc < MIN_MOMENTUM:
            log(f"skip {sym}: momentum {sc}")
            continue
        size = rm.size_usd(eq, broker.cash, False)
        price = float(inp.pair["priceUsd"])
        broker.buy(mint, sym, size, price, lane="C")
        day.fees_spent += broker.fee_usd
        log(f"BUY {sym} ${size:.2f} @ {price:.8g} momentum {sc} ({', '.join(notes)})")
        time.sleep(1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=0, help="0 = run forever")
    ap.add_argument("--interval", type=int, default=90)
    a = ap.parse_args()
    if not CONFIG.paper_mode:
        raise SystemExit("Live mode is not implemented yet. Paper only.")
    broker, rm = PaperBroker(), RiskManager()
    day = DayState(today(), broker.equity({}))
    n = 0
    while True:
        if day.day != today():
            day = DayState(today(), broker.equity({}))
        prices = manage_exits(broker, rm, day)
        look_for_entries(broker, rm, day, prices)
        eq = broker.equity(prices)
        log(f"equity ${eq:.2f} cash ${broker.cash:.2f} open {len(broker.positions)} fees ${broker.fees_total:.2f}")
        n += 1
        if a.cycles and n >= a.cycles:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
