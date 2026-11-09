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
