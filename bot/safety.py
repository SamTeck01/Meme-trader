"""Safety filter (STRATEGY.md §2). Pure decision logic + a fetcher that gathers inputs.

HARD checks can never be skipped. SOFT checks may be skipped by the conviction lane.
"""
from dataclasses import dataclass, field

from .config import CONFIG, SafetyConfig
from .data import dexscreener, rugcheck, jupiter

POOL_TYPES = {"AMM", "LOCKER", "PUMP_FUN", "BONDING_CURVE"}
SELL_TEST_USD = 5.0


@dataclass
class SafetyInputs:
    mint: str
    report: dict | None          # RugCheck full report
    pair: dict | None            # best DexScreener pair
    sell_quote: dict | None      # Jupiter quote for selling ~$5 of the token
    sell_test_attempted: bool = True


@dataclass
class SafetyResult:
    mint: str
    passed: bool
    hard_fails: list[str] = field(default_factory=list)
    soft_fails: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        reasons = self.hard_fails + [f"(soft) {s}" for s in self.soft_fails]
        return f"{status} {self.mint[:8]}… " + ("; ".join(reasons) if reasons else "all checks ok")


def _excluded_owners(report: dict) -> set[str]:
    known = report.get("knownAccounts") or {}
    return {addr for addr, info in known.items() if (info or {}).get("type") in POOL_TYPES}


def top10_pct(report: dict) -> float:
    excluded = _excluded_owners(report)
    holders = [h for h in (report.get("topHolders") or [])
               if h.get("owner") not in excluded and h.get("address") not in excluded]
    return sum(float(h.get("pct") or 0) for h in holders[:10])


def cluster_pct(report: dict) -> float:
    supply = float(((report.get("token") or {}).get("supply")) or 0)
    if supply <= 0:
        return 0.0
    held = sum(float(n.get("currentHolding") or 0) for n in (report.get("insiderNetworks") or []))
    return held / supply * 100


def creator_pct(report: dict) -> float:
    supply = float(((report.get("token") or {}).get("supply")) or 0)
    bal = float(report.get("creatorBalance") or 0)
    return bal / supply * 100 if supply > 0 else 0.0


def evaluate(inp: SafetyInputs, conviction: bool = False, cfg: SafetyConfig = CONFIG.safety,
             on_curve: bool = False) -> SafetyResult:
    """on_curve: token still on the pump.fun bonding curve. The curve program always
    lets holders sell, so the sell test is satisfied by verifying the launchpad, and the
    DEX-liquidity check does not apply."""
    res = SafetyResult(mint=inp.mint, passed=False)
    r, p = inp.report, inp.pair

    # ---------- HARD (never skipped) ----------
    if not r:
        res.hard_fails.append("no rugcheck report")
        return res
    token = r.get("token") or {}
    if token.get("mintAuthority") or r.get("mintAuthority"):
        res.hard_fails.append("mint authority NOT revoked")
    if token.get("freezeAuthority") or r.get("freezeAuthority"):
        res.hard_fails.append("freeze authority NOT revoked")
    if r.get("rugged"):
        res.hard_fails.append("already flagged rugged")
    tf = r.get("transferFee") or {}
    if float(tf.get("pct") or 0) > 0:
        res.hard_fails.append(f"transfer tax {tf.get('pct')}%")
    cpct = cluster_pct(r)
    res.metrics["cluster_pct"] = round(cpct, 2)
    if cpct > cfg.max_cluster_pct:
        res.hard_fails.append(f"insider cluster holds {cpct:.1f}%")
    q = inp.sell_quote
    is_pump = ((r.get("launchpad") or {}).get("platform")) == "pump_fun"
    if on_curve and not is_pump:
        res.hard_fails.append("claimed curve token but launchpad is not pump.fun")
    elif on_curve and (not q or "outAmount" not in q):
        res.metrics["sell_test"] = "pump.fun curve"
    elif not q or "outAmount" not in q:
        res.hard_fails.append("sell test failed (no route to sell)")
    else:
        impact = float(q.get("priceImpactPct") or 0) * 100
        res.metrics["sell_impact_pct"] = round(impact, 2)
        if impact > cfg.max_sell_price_impact_pct:
            res.hard_fails.append(f"sell price impact {impact:.1f}%")

    # ---------- SOFT (conviction may skip) ----------
    t10 = top10_pct(r)
    res.metrics["top10_pct"] = round(t10, 2)
    if t10 > cfg.max_top10_pct:
        res.soft_fails.append(f"top10 hold {t10:.1f}%")
    crp = creator_pct(r)
    res.metrics["creator_pct"] = round(crp, 2)
    if crp > cfg.max_creator_pct:
        res.soft_fails.append(f"creator holds {crp:.1f}%")
    liq = float(((p or {}).get("liquidity") or {}).get("usd") or 0)
    res.metrics["liquidity_usd"] = round(liq)
    if liq < cfg.min_liquidity_usd and not on_curve:
        res.soft_fails.append(f"liquidity ${liq:,.0f}")
    ch24 = float(((p or {}).get("priceChange") or {}).get("h24") or 0)
    res.metrics["change_24h_pct"] = ch24
    if ch24 > cfg.max_price_change_24h_pct:
        res.soft_fails.append(f"already +{ch24:.0f}% in 24h")
    for risk in r.get("risks") or []:
        if risk.get("level") == "danger":
            res.soft_fails.append(f"rugcheck: {risk.get('name')}")

    res.passed = not res.hard_fails and (conviction or not res.soft_fails)
    return res


def gather(mint: str) -> SafetyInputs:
    """Fetch everything the filter needs from free APIs."""
    report = rugcheck.report(mint)
    pair = dexscreener.best_pair(mint)
    sell_q = None
    try:
        price = float((pair or {}).get("priceUsd") or 0)
        decimals = int(((report or {}).get("token") or {}).get("decimals") or 0)
        if price > 0:
            raw = int(SELL_TEST_USD / price * (10 ** decimals))
            if raw > 0:
                sell_q = jupiter.sell_quote(mint, raw)
    except Exception:
        sell_q = None
    return SafetyInputs(mint=mint, report=report, pair=pair, sell_quote=sell_q)


def check(mint: str, conviction: bool = False, on_curve: bool = False) -> SafetyResult:
    return evaluate(gather(mint), conviction=conviction, on_curve=on_curve)
