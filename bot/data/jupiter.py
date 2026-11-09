"""Jupiter swap quotes (free lite API). Used for the sell test and, later, execution."""
from .http import get_json
from ..config import SOL_MINT

BASE = "https://lite-api.jup.ag/swap/v1"


def quote(input_mint: str, output_mint: str, amount: int, slippage_bps: int = 500) -> dict | None:
    return get_json(f"{BASE}/quote", params={
        "inputMint": input_mint, "outputMint": output_mint,
        "amount": str(amount), "slippageBps": str(slippage_bps),
    })


def sell_quote(mint: str, raw_amount: int) -> dict | None:
    """Quote selling `raw_amount` (in token base units) of `mint` for SOL."""
    return quote(mint, SOL_MINT, raw_amount)
