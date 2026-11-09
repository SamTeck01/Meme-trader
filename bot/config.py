"""All tunable numbers live here. Values mirror STRATEGY.md."""
from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class SafetyConfig:
    # Non-negotiable (never skipped, even for conviction trades)
    max_cluster_pct: float = 30.0          # insider/bundle network share of supply
    # Standard (conviction lane may skip)
    max_top10_pct: float = 30.0            # top 10 holders, excluding pools/curve
    max_creator_pct: float = 5.0
    min_liquidity_usd: float = 10_000.0    # enough to exit a ~$3-6 position cleanly
    max_price_change_24h_pct: float = 900.0  # skip if already >10x today
    max_sell_price_impact_pct: float = 10.0  # for the sell-test quote


@dataclass(frozen=True)
class Config:
    paper_mode: bool = os.getenv("PAPER_MODE", "true").lower() != "false"
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    http_timeout_s: float = 15.0


CONFIG = Config()

SOL_MINT = "So11111111111111111111111111111111111111112"


@dataclass(frozen=True)
class RiskConfig:
    normal_size_pct: float = 15.0
    conviction_size_pct: float = 30.0
    max_open: int = 4
    max_open_conviction: int = 1
    stop_loss_pct: float = -30.0
    conviction_stop_loss_pct: float = -40.0
    tp1_multiple: float = 2.0      # sell tp1_fraction at 2x
    tp1_fraction: float = 0.5
    tp2_multiple: float = 4.0      # sell tp2_fraction (of original) at 4x
    tp2_fraction: float = 0.25
    trailing_stop_pct: float = 35.0  # remainder: exit if falls 35% from peak
    time_stop_hours: float = 6.0
    time_stop_flat_band_pct: float = 20.0  # "flat" = within ±20%
    daily_loss_stop_pct: float = -25.0
    conviction_loss_streak_stop: int = 2
    hard_floor_usd: float = 8.0
    daily_fee_budget_pct: float = 10.0
    est_fee_per_trade_usd: float = 0.25   # priority + network, per swap
    min_position_usd: float = 1.0


RISK = RiskConfig()
