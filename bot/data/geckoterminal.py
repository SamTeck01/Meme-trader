"""GeckoTerminal free API (~30 req/min): OHLCV candles for the Aroon filter."""
from .http import get_json

BASE = "https://api.geckoterminal.com/api/v2"


def candles(pool: str, timeframe: str = "minute", aggregate: int = 5, limit: int = 30,
            network: str = "solana") -> list[list[float]]:
    """Oldest-first [ts, open, high, low, close, volume]."""
    d = get_json(f"{BASE}/networks/{network}/pools/{pool}/ohlcv/{timeframe}",
                 params={"aggregate": aggregate, "limit": limit})
    rows = (((d or {}).get("data") or {}).get("attributes") or {}).get("ohlcv_list") or []
    return sorted(rows, key=lambda r: r[0])
