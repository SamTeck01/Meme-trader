"""DexScreener free API: boosts, trending profiles, pair data."""
from .http import get_json

BASE = "https://api.dexscreener.com"


def latest_boosts(chain: str = "solana") -> list[dict]:
    data = get_json(f"{BASE}/token-boosts/latest/v1") or []
    return [x for x in data if x.get("chainId") == chain]


def top_boosts(chain: str = "solana") -> list[dict]:
    data = get_json(f"{BASE}/token-boosts/top/v1") or []
    return [x for x in data if x.get("chainId") == chain]


def latest_profiles(chain: str = "solana") -> list[dict]:
    data = get_json(f"{BASE}/token-profiles/latest/v1") or []
    return [x for x in data if x.get("chainId") == chain]


def token_pairs(mint: str, chain: str = "solana") -> list[dict]:
    return get_json(f"{BASE}/tokens/v1/{chain}/{mint}") or []


def best_pair(mint: str) -> dict | None:
    """Most liquid pair for the token."""
    pairs = token_pairs(mint)
    if not pairs:
        return None
    return max(pairs, key=lambda p: (p.get("liquidity") or {}).get("usd") or 0)


def pairs_for(mints: list[str], chain: str = "solana") -> list[dict]:
    """All pairs for up to 30 tokens in one call (used by the shadow tracker)."""
    return get_json(f"{BASE}/tokens/v1/{chain}/{','.join(mints[:30])}") or []
