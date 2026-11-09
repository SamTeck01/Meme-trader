"""Append-only log of every reviewed token: rule decision vs AI decision.
Used for the go-live test: AI must beat the 'no-AI' baseline (STRATEGY.md §10)."""
import json
from datetime import datetime, timezone
from pathlib import Path

LOG = Path("data/decisions.jsonl")


def record(entry: dict, path: Path = LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), **entry}, default=str) + "\n")
