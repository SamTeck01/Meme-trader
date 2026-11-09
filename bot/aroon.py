"""Aroon trend filter: direction (Up vs Down) -> strength (oscillator) -> filter.

Aroon Up   = 100 * (period - bars since highest high) / period
Aroon Down = 100 * (period - bars since lowest low)  / period
Oscillator = Up - Down   (+100 strong uptrend ... -100 strong downtrend)
"""
import os

PERIOD = 14
STRONG = 40          # |oscillator| >= 40 counts as a clear trend
ENABLED = os.getenv("AROON_FILTER", "true").lower() != "false"


def aroon(highs: list[float], lows: list[float], period: int = PERIOD) -> tuple[float, float, float] | None:
    """Uses the last period+1 bars (oldest-first). Returns (up, down, oscillator)."""
    if len(highs) < period + 1 or len(lows) < period + 1:
        return None
    h, lo = highs[-(period + 1):], lows[-(period + 1):]
    since_high = period - max(range(len(h)), key=lambda i: (h[i], i))
    since_low = period - min(range(len(lo)), key=lambda i: (lo[i], -i))
    up = 100 * (period - since_high) / period
    down = 100 * (period - since_low) / period
    return up, down, up - down


def adjust(score: int, candles: list[list[float]]) -> tuple[int, str, bool]:
    """Apply the filter to a momentum score. Returns (new_score, note, blocked)."""
    if not ENABLED:
        return score, "aroon off", False
    a = aroon([c[2] for c in candles], [c[3] for c in candles])
    if a is None:
        return score, "aroon n/a (too few candles)", False
    up, down, osc = a
    note = f"aroon {osc:+.0f} (up {up:.0f}/down {down:.0f})"
    if osc <= -STRONG:
        return score, note + " downtrend", True
    if osc >= STRONG:
        return score + 15, note + " uptrend", False
    return score - 10, note + " no clear trend", False
