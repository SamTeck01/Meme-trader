"""RugCheck free API: full token risk report."""
from .http import get_json

BASE = "https://api.rugcheck.xyz/v1"


def report(mint: str) -> dict | None:
    return get_json(f"{BASE}/tokens/{mint}/report")
