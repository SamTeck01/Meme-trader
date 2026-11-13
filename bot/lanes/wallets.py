"""Lane A: smart-wallet copy (STRATEGY.md §1A).

Polls Helius' parsed-transactions API (free tier) for each tracked wallet instead of
webhooks, so the bot needs no public URL. A wallet gaining a token while paying SOL/stables
= buy signal; the reverse = sell signal (used for the copy exit).

Wallets: WALLETS env (comma-separated) or config/wallets.txt (one address per line, # comments).
"""
import os
import time
from dataclasses import dataclass
from pathlib import Path

from ..config import SOL_MINT
from ..data.http import get_json

HELIUS = "https://api.helius.xyz/v0/addresses/{a}/transactions"
IGNORE = {SOL_MINT,
          "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",   # USDC
          "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCQ6tymYJCX"}   # USDT
MAX_SIGNAL_AGE_S = 10 * 60
MIN_BASE = 0.005   # ignore dust: fees alone are not a purchase
WALLETS_FILE = Path("config/wallets.txt")


@dataclass
class WalletEvent:
    wallet: str
    mint: str
    side: str        # BUY | SELL
    ts: int
    sig: str


def load_wallets() -> list[str]:
    env = os.getenv("WALLETS", "")
    ws = [w.strip() for w in env.split(",") if w.strip()]
    if not ws and WALLETS_FILE.exists():
        ws = [l.split("#")[0].strip() for l in WALLETS_FILE.read_text().splitlines()]
    return [w for w in ws if w]


def _flows(tx: dict, wallet: str) -> tuple[dict[str, float], float]:
    """(net token change per non-base mint, net base-currency flow) for the wallet.
    Base flow is in mixed units (SOL + stables); only its sign is used."""
    tokens: dict[str, float] = {}
    base = 0.0
    for t in tx.get("tokenTransfers") or []:
        mint, amt = t.get("mint"), float(t.get("tokenAmount") or 0)
        d = amt if t.get("toUserAccount") == wallet else -amt if t.get("fromUserAccount") == wallet else 0.0
        if not mint or not d:
            continue
        if mint in IGNORE:
            base += d
        else:
            tokens[mint] = tokens.get(mint, 0.0) + d
    for a in tx.get("accountData") or []:
        if a.get("account") == wallet:
            base += float(a.get("nativeBalanceChange") or 0) / 1e9
    return tokens, base


def parse_tx(tx: dict, wallet: str) -> list[WalletEvent]:
    """A real trade moves a token one way and SOL/stables the other. Helius labels many
    swaps TRANSFER/UNKNOWN, so we classify by money flow, not by its type field. This also
    ignores airdrops/spam (token in, nothing paid) and multi-hop route tokens (net zero)."""
    if tx.get("transactionError"):
        return []
    tokens, base = _flows(tx, wallet)
    out = []
    for mint, d in tokens.items():
        if d > 1e-9 and base < -MIN_BASE:
            side = "BUY"
        elif d < -1e-9 and base > MIN_BASE:
            side = "SELL"
        else:
            continue
        out.append(WalletEvent(wallet, mint, side, int(tx.get("timestamp") or 0), tx.get("signature", "")))
    return out


class WalletLane:
    def __init__(self, wallets: list[str] | None = None, api_key: str | None = None):
        self.wallets = wallets if wallets is not None else load_wallets()
        self.key = api_key or os.getenv("HELIUS_API_KEY", "")
        self.last_sig: dict[str, str] = {}
        self.buys: dict[str, set[str]] = {}      # mint -> wallets that bought recently
        self.buy_ts: dict[str, float] = {}
        self.sold: set[tuple[str, str]] = set()  # (wallet, mint)
        self.stats = {"wallets": len(self.wallets), "buys": 0, "sells": 0, "errors": 0}

    @property
    def enabled(self) -> bool:
        return bool(self.key and self.wallets)

    def ingest(self, events: list[WalletEvent], now: float | None = None) -> None:
        now = now or time.time()
        for e in events:
            if e.side == "BUY":
                if now - e.ts > MAX_SIGNAL_AGE_S:
                    continue
                self.buys.setdefault(e.mint, set()).add(e.wallet)
                self.buy_ts[e.mint] = now
                self.sold.discard((e.wallet, e.mint))
                self.stats["buys"] += 1
            else:
                self.sold.add((e.wallet, e.mint))
                self.stats["sells"] += 1

    def poll(self) -> None:
        if not self.enabled:
            return
        for w in self.wallets:
            try:
                txs = get_json(HELIUS.format(a=w), params={"api-key": self.key, "limit": 50}) or []
            except Exception:
                self.stats["errors"] += 1
                continue
            first_run = w not in self.last_sig
            new = []
            for tx in txs:                       # newest first
                if tx.get("signature") == self.last_sig.get(w):
                    break
                new.append(tx)
            if txs:
                self.last_sig[w] = txs[0].get("signature", "")
            if first_run:
                # don't copy history; only remember sells so we don't follow stale buys
                continue
            for tx in reversed(new):
                self.ingest(parse_tx(tx, w))

    def candidates(self) -> list[tuple[str, set[str]]]:
        """Fresh buy signals: [(mint, wallets)] — consumed once returned."""
        now = time.time()
        out = [(m, ws) for m, ws in self.buys.items() if now - self.buy_ts.get(m, 0) <= MAX_SIGNAL_AGE_S]
        self.buys.clear()
        return out

    def wallet_sold(self, wallet: str | None, mint: str) -> bool:
        return bool(wallet) and (wallet, mint) in self.sold
