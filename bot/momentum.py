"""Lane C momentum score from DexScreener pair data (0-100). Pure function."""


def score(pair: dict) -> tuple[int, list[str]]:
    tx = pair.get("txns") or {}
    vol = pair.get("volume") or {}
    ch = pair.get("priceChange") or {}
    notes, s = [], 0
    h1 = tx.get("h1") or {}
    buys, sells = h1.get("buys") or 0, h1.get("sells") or 0
    if sells and buys / sells >= 1.3:
        s += 25; notes.append(f"buy/sell {buys}/{sells}")
    v1, v6 = float(vol.get("h1") or 0), float(vol.get("h6") or 0)
    if v6 and v1 > v6 / 6 * 1.5:
        s += 25; notes.append("volume accelerating")
    c5, c1 = float(ch.get("m5") or 0), float(ch.get("h1") or 0)
    if c1 > 5:
        s += 20; notes.append(f"1h +{c1:.0f}%")
    if -8 < c5 < 15:
        s += 15; notes.append("not mid-spike")
    if float((pair.get("liquidity") or {}).get("usd") or 0) > 30_000:
        s += 15; notes.append("solid liquidity")
    return s, notes
