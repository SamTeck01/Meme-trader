"""Paper broker: simulates fills on live prices with realistic slippage and fees.

State persists to a JSON file so a restart doesn't lose the paper account.
The live broker (Jupiter swaps) will implement the same buy/sell interface.
"""
import json
import random
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .config import RISK
from .risk import Position

STATE_FILE = Path("data/paper_state.json")


class PaperBroker:
    def __init__(self, start_usd: float = 20.0, state_file: Path = STATE_FILE,
                 slippage_range=(0.03, 0.10), fee_usd: float = RISK.est_fee_per_trade_usd,
                 rng: random.Random | None = None):
        self.state_file = state_file
        self.slippage_range = slippage_range
        self.fee_usd = fee_usd
        self.rng = rng or random.Random()
        self.cash = start_usd
        self.positions: dict[str, Position] = {}
        self.trades: list[dict] = []
        self.fees_total = 0.0
        self._load()

    # ---------- trading ----------
    def _slip(self) -> float:
        return self.rng.uniform(*self.slippage_range)

    def buy(self, mint: str, symbol: str, usd: float, price: float, lane: str,
            conviction: bool = False, copied_wallet: str | None = None) -> Position:
        if usd + self.fee_usd > self.cash:
            raise ValueError("insufficient paper cash")
        fill = price * (1 + self._slip())
        tokens = usd / fill
        self.cash -= usd + self.fee_usd
        self.fees_total += self.fee_usd
        p = Position(mint=mint, symbol=symbol, lane=lane, conviction=conviction,
                     entry_price=fill, tokens=tokens, initial_tokens=tokens, cost_usd=usd,
                     opened_at=datetime.now(timezone.utc), peak_price=fill,
                     copied_wallet=copied_wallet)
        self.positions[mint] = p
        self._log("BUY", p, usd, fill, "entry")
        self._save()
        return p

    def sell(self, mint: str, fraction: float, price: float, reason: str) -> float:
        """Sell a fraction of the current holding. Returns realized USD (after fee)."""
        p = self.positions[mint]
        qty = p.tokens * min(max(fraction, 0.0), 1.0)
        fill = price * (1 - self._slip())
        proceeds = qty * fill - self.fee_usd
        self.cash += proceeds
        self.fees_total += self.fee_usd
        p.tokens -= qty
        self._log("SELL", p, proceeds, fill, reason)
        if p.tokens <= p.initial_tokens * 1e-6:
            del self.positions[mint]
        self._save()
        return proceeds

    def realized_pnl(self, mint: str) -> float:
        buys = sum(t["usd"] + self.fee_usd for t in self.trades if t["mint"] == mint and t["side"] == "BUY")
        sells = sum(t["usd"] for t in self.trades if t["mint"] == mint and t["side"] == "SELL")
        return sells - buys

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(p.value(prices.get(m, p.entry_price)) for m, p in self.positions.items())

    # ---------- persistence ----------
    def _log(self, side, p, usd, fill, reason):
        self.trades.append({"ts": datetime.now(timezone.utc).isoformat(), "side": side, "mint": p.mint,
                            "symbol": p.symbol, "lane": p.lane, "usd": round(usd, 4),
                            "price": fill, "reason": reason})

    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        pos = {m: {**asdict(p), "opened_at": p.opened_at.isoformat()} for m, p in self.positions.items()}
        self.state_file.write_text(json.dumps({"cash": self.cash, "fees_total": self.fees_total,
                                               "positions": pos, "trades": self.trades}, indent=1))

    def _load(self):
        if not self.state_file.exists():
            return
        d = json.loads(self.state_file.read_text())
        self.cash, self.fees_total, self.trades = d["cash"], d["fees_total"], d["trades"]
        for m, p in d["positions"].items():
            p["opened_at"] = datetime.fromisoformat(p["opened_at"])
            self.positions[m] = Position(**p)
