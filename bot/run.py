"""Main loop (paper mode).

Lanes: A (smart-wallet copy, Helius), B (pump.fun curve), C (trending momentum),
D (hype/conviction). Rules + safety decide first; the AI judge can only veto.
Telegram: alerts + owner commands.
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
from .lanes.wallets import WalletLane
from .ai import judge as ai_judge, decisions
from .telegram import Telegram, HELP
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
    wallets: set = field(default_factory=set)
    note: str = ""


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%H:%M:%S} {msg}", flush=True)


def sol_usd() -> float:
    p = dexscreener.best_pair(SOL_MINT)
    return float(p["priceUsd"]) if p and p.get("priceUsd") else 0.0


def price_of(mint: str) -> float | None:
    p = dexscreener.best_pair(mint)
    return float(p["priceUsd"]) if p and p.get("priceUsd") else None


TG = Telegram()


def manage_exits(broker: PaperBroker, rm: RiskManager, day: DayState,
                 wl: WalletLane | None = None) -> dict[str, float]:
    prices = {}
    for mint, p in list(broker.positions.items()):
        price = price_of(mint)
        if price is None:
            continue
        prices[mint] = price
        copied_sold = bool(wl and wl.wallet_sold(p.copied_wallet, mint))
        act = rm.check_exit(p, price, datetime.now(timezone.utc), copied_wallet_sold=copied_sold)
        if act:
            got = broker.sell(mint, act.fraction, price, act.reason)
            day.fees_spent += broker.fee_usd
            log(f"SELL {p.symbol} {act.fraction:.0%} @ {price:.8g} ({act.reason}) ${got:.2f}")
            TG.send(f"SELL {p.symbol} {act.fraction:.0%} ({act.reason}) ${got:.2f}")
            if mint not in broker.positions:
                pnl = broker.realized_pnl(mint)
                rm.record_close(p, pnl, day)
                log(f"CLOSED {p.symbol} [{p.lane}] P&L ${pnl:+.2f}")
                TG.send(f"CLOSED {p.symbol} [{p.lane}] P&L ${pnl:+.2f}")
    return prices


def gather_candidates(pump: PumpLane, wl: WalletLane | None = None) -> list[Candidate]:
    out = [Candidate(m, "A", wallets=ws, note=f"{len(ws)} smart wallet(s) bought")
           for m, ws in (wl.candidates() if wl else [])]
    out += [Candidate(t.mint, "B", on_curve=True, curve_price_sol=t.price_sol,
                     note=f"curve {t.progress:.0%}, {len(t.buyers)} buyers") for t in pump.candidates()]
    for mint, info in hype.collect().items():
        out.append(Candidate(mint, "CD", hype_info=info))
    return out


def decide(c: Candidate, inp: safety.SafetyInputs) -> tuple[bool, bool, str, str]:
    """Returns (buy, conviction, symbol, reason). AI judge will be added here."""
    sym = ((inp.pair or {}).get("baseToken") or {}).get("symbol") or "?"
    if c.lane == "A":
        res = safety.evaluate(inp)
        return res.passed, False, sym, res.summary() if not res.passed else c.note
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


def ai_review(c: Candidate, inp: safety.SafetyInputs, lane: str, reason: str):
    """Returns (allowed, verdict). No AI configured -> allowed (no-AI baseline)."""
    res = safety.evaluate(inp, conviction=(lane == "D"), on_curve=c.on_curve)
    extra = {"smart_wallets": len(c.wallets)} if c.wallets else {}
    if c.hype_info:
        extra["hype"] = {k: sorted(v) if isinstance(v, set) else v for k, v in c.hype_info.items()}
    v = ai_judge.judge(ai_judge.candidate_summary(c.mint, lane, inp.pair, res.metrics, reason, extra))
    return (True if v is None else v.buy), v


def look_for_entries(broker, rm, day, prices, pump, seen: dict, wl=None) -> None:
    cands = gather_candidates(pump, wl)
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
        lane = "D" if conviction else (c.lane if c.lane in ("A", "B") else "C")
        entry = {"mint": c.mint, "symbol": sym, "lane": lane, "rules_buy": buy, "reason": reason}
        if not buy:
            decisions.record(entry)
            log(f"skip {sym} [{c.lane}]: {reason[:120]}")
            continue
        allowed, v = ai_review(c, inp, lane, reason)
        if v:
            entry["ai"] = {"decision": v.decision, "confidence": v.confidence,
                           "red_flags": v.red_flags, "reason": v.reason, "model": v.model}
        entry["ai_buy"] = allowed
        decisions.record(entry)
        if not allowed:
            log(f"AI skip {sym} [{lane}] {v.confidence}: {v.reason[:100]}")
            continue
        if v:
            reason += f" | AI {v.confidence}: {v.reason}"
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
        size = rm.size_usd(eq, broker.cash, conviction)
        copied = next(iter(sorted(c.wallets)), None)
        broker.buy(c.mint, sym, size, price, lane=lane, conviction=conviction, copied_wallet=copied)
        day.fees_spent += broker.fee_usd
        log(f"BUY {sym} [{lane}] ${size:.2f} @ {price:.8g} — {reason}")
        TG.send(f"BUY {sym} [{lane}] ${size:.2f}\n{reason[:300]}\nhttps://dexscreener.com/solana/{c.mint}")


def handle_commands(broker, rm, day, prices) -> None:
    for cmd, arg in TG.pending():
        eq = broker.equity(prices)
        if cmd == "stop":
            rm.killed = True
            for mint, p in list(broker.positions.items()):
                px = prices.get(mint) or price_of(mint) or p.entry_price
                broker.sell(mint, 1.0, px, "manual /stop")
            TG.send(f"STOPPED. Everything sold. Cash ${broker.cash:.2f}. /start to resume.")
        elif cmd == "start":
            rm.killed = False
            TG.send("Resumed (risk limits still apply).")
        elif cmd == "status":
            mode = "PAPER" if CONFIG.paper_mode else "LIVE"
            state = "STOPPED" if rm.killed else ("daily stop" if day.halted else "running")
            TG.send(f"{mode} · {state}\nequity ${eq:.2f} · cash ${broker.cash:.2f} · open {len(broker.positions)}"
                    f"\nfees today ${day.fees_spent:.2f} · AI {'on' if ai_judge.enabled() else 'off'}")
        elif cmd == "positions":
            lines = [f"{p.symbol} [{p.lane}] ${p.cost_usd:.2f} → {p.multiple(prices.get(m, p.entry_price)):.2f}x"
                     for m, p in broker.positions.items()]
            TG.send("\n".join(lines) or "no open positions")
        elif cmd == "pnl":
            TG.send(f"today {(eq / day.start_balance - 1) * 100:+.1f}% (${eq - day.start_balance:+.2f})"
                    f"\nall-time ${eq - 20:+.2f} · fees paid ${broker.fees_total:.2f}")
        elif cmd in ("watch", "unwatch") and arg:
            key = arg if len(arg) > 30 else arg.lstrip("$").lower()
            (hype.WATCHLIST.add if cmd == "watch" else hype.WATCHLIST.discard)(key)
            TG.send(f"{cmd}ed {arg}. Watchlist: {', '.join(sorted(hype.WATCHLIST)) or 'empty'}")
        else:
            TG.send(HELP)


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
    wl = WalletLane()
    TG.start()
    log(f"lane A: {'on' if wl.enabled else 'off (needs HELIUS_API_KEY + wallets)'} · "
        f"AI judge: {'on' if ai_judge.enabled() else 'off (no-AI baseline)'} · telegram: {'on' if TG.enabled else 'off'}")
    TG.send("Meme Trader started (PAPER). /help")
    day = DayState(today(), broker.equity({}))
    seen: dict[str, float] = {}
    n = 0
    while True:
        if day.day != today():
            eq = broker.equity({})
            TG.send(f"Daily summary {day.day}: ${day.start_balance:.2f} → ${eq:.2f} "
                    f"({(eq / day.start_balance - 1) * 100:+.1f}%), fees ${day.fees_spent:.2f}")
            day = DayState(today(), eq)
        wl.poll()
        prices = manage_exits(broker, rm, day, wl)
        handle_commands(broker, rm, day, prices)
        pump.poll(sol_usd())
        look_for_entries(broker, rm, day, prices, pump, seen, wl)
        eq = broker.equity(prices)
        log(f"equity ${eq:.2f} cash ${broker.cash:.2f} open {len(broker.positions)} "
            f"fees ${broker.fees_total:.2f} | pump: {pump.stats}")
        n += 1
        if a.cycles and n >= a.cycles:
            break
        for _ in range(a.interval):   # stay responsive to Telegram commands
            time.sleep(1)
            if not TG.commands.empty():
                handle_commands(broker, rm, day, prices)


if __name__ == "__main__":
    main()
