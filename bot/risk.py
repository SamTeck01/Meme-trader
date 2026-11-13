"""Risk manager (STRATEGY.md §5–5b). The AI never overrides anything in here."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .config import RISK, RiskConfig


@dataclass
class Position:
    mint: str
    symbol: str
    lane: str
    conviction: bool
    entry_price: float
    tokens: float            # current token amount held
    initial_tokens: float
    cost_usd: float
    opened_at: datetime
    peak_price: float = 0.0
    tp1_done: bool = False
    tp2_done: bool = False
    copied_wallet: str | None = None

    def value(self, price: float) -> float:
        return self.tokens * price

    def multiple(self, price: float) -> float:
        return price / self.entry_price if self.entry_price else 0.0


@dataclass
class ExitAction:
    fraction: float          # fraction of CURRENT holding to sell
    reason: str


@dataclass
class DayState:
    day: str
    start_balance: float
    fees_spent: float = 0.0
    conviction_loss_streak: int = 0
    conviction_paused: bool = False
    halted: bool = False     # daily stop hit


@dataclass
class RiskManager:
    cfg: RiskConfig = field(default_factory=lambda: RISK)
    killed: bool = False     # hard floor or manual /stop

    # ---------- entries ----------
    def can_open(self, balance: float, equity: float, positions: list[Position],
                 day: DayState, conviction: bool) -> tuple[bool, str]:
        c = self.cfg
        if self.killed:
            return False, "bot stopped"
        if equity < c.hard_floor_usd:
            self.killed = True
            return False, f"hard floor: equity ${equity:.2f} < ${c.hard_floor_usd}"
        if day.halted:
            return False, "daily loss stop active"
        if (equity / day.start_balance - 1) * 100 <= c.daily_loss_stop_pct:
            day.halted = True
            return False, "daily loss stop hit"
        if len(positions) >= c.max_open:
            return False, "max open positions"
        if conviction:
            if day.conviction_paused:
                return False, "conviction lane paused (loss streak)"
            if sum(p.conviction for p in positions) >= c.max_open_conviction:
                return False, "conviction slot full"
        budget = day.start_balance * c.daily_fee_budget_pct / 100
        if day.fees_spent + 2 * c.est_fee_per_trade_usd > budget:
            return False, "daily fee budget used up"
        if self.size_usd(equity, balance, conviction) < c.min_position_usd:
            return False, "position too small"
        return True, "ok"

    def size_usd(self, equity: float, balance: float, conviction: bool) -> float:
        pct = self.cfg.conviction_size_pct if conviction else self.cfg.normal_size_pct
        return min(equity * pct / 100, balance - self.cfg.est_fee_per_trade_usd)

    # ---------- exits ----------
    def check_exit(self, p: Position, price: float, now: datetime,
                   copied_wallet_sold: bool = False) -> ExitAction | None:
        c = self.cfg
        p.peak_price = max(p.peak_price, price)
        m = p.multiple(price)
        sl = c.conviction_stop_loss_pct if p.conviction else c.stop_loss_pct
        if (m - 1) * 100 <= sl:
            return ExitAction(1.0, f"stop-loss {sl:.0f}%")
        if copied_wallet_sold:
            return ExitAction(1.0, "copied wallet sold")
        if not p.tp1_done and m >= c.tp1_multiple:
            p.tp1_done = True
            return ExitAction(c.tp1_fraction, f"take profit {c.tp1_multiple:g}x")
        if p.tp1_done and not p.tp2_done and m >= c.tp2_multiple:
            p.tp2_done = True
            frac_of_current = c.tp2_fraction / (1 - c.tp1_fraction)
            return ExitAction(min(frac_of_current, 1.0), f"take profit {c.tp2_multiple:g}x")
        if p.tp1_done and p.peak_price and price <= p.peak_price * (1 - c.trailing_stop_pct / 100):
            return ExitAction(1.0, f"trailing stop -{c.trailing_stop_pct:.0f}% from peak")
        hours = (now - p.opened_at).total_seconds() / 3600
        if hours >= c.time_stop_hours and abs((m - 1) * 100) <= c.time_stop_flat_band_pct:
            return ExitAction(1.0, "time stop (flat)")
        return None

    def record_close(self, p: Position, pnl_usd: float, day: DayState) -> None:
        if not p.conviction:
            return
        if pnl_usd < 0:
            day.conviction_loss_streak += 1
            if day.conviction_loss_streak >= self.cfg.conviction_loss_streak_stop:
                day.conviction_paused = True
        else:
            day.conviction_loss_streak = 0


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
