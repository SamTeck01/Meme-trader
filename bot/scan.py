"""Step-1 runner: pull boosted/trending Solana tokens and run the safety filter.

Usage: python -m bot.scan [--limit N]
"""
import argparse
import time

from .data import dexscreener
from . import safety


def candidates(limit: int) -> list[str]:
    seen: list[str] = []
    for src in (dexscreener.latest_boosts, dexscreener.top_boosts, dexscreener.latest_profiles):
        try:
            for item in src():
                m = item.get("tokenAddress")
                if m and m not in seen:
                    seen.append(m)
        except Exception as e:
            print(f"source error: {e}")
    return seen[:limit]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args()
    mints = candidates(args.limit)
    print(f"Checking {len(mints)} tokens…\n")
    passed = 0
    for m in mints:
        try:
            res = safety.check(m)
        except Exception as e:
            print(f"ERROR {m[:8]}… {e}")
            continue
        passed += res.passed
        print(res.summary(), res.metrics)
        time.sleep(1.2)  # be gentle with free APIs
    print(f"\n{passed}/{len(mints)} passed the safety filter")


if __name__ == "__main__":
    main()
