"""Lane D: hype / conviction from free sources (no X API).

Signals: DexScreener paid boosts (someone is spending money to promote it), presence of
socials/website, appearing in several lists at once, and the user's /watch list.
"""
from ..data import dexscreener

WATCHLIST: set[str] = set()   # mints or symbols added via Telegram /watch (lower-case symbols)


def collect() -> dict[str, dict]:
    """mint -> {boost, sources, links}"""
    out: dict[str, dict] = {}
    for name, fn in (("latest_boost", dexscreener.latest_boosts), ("top_boost", dexscreener.top_boosts),
                     ("profile", dexscreener.latest_profiles)):
        try:
            items = fn()
        except Exception:
            continue
        for it in items:
            m = it.get("tokenAddress")
            if not m:
                continue
            d = out.setdefault(m, {"boost": 0.0, "sources": set(), "links": set()})
            d["sources"].add(name)
            d["boost"] = max(d["boost"], float(it.get("totalAmount") or 0))
            for link in it.get("links") or []:
                d["links"].add(link.get("type") or "website")
    return out


def hype_score(info: dict, symbol: str = "", mint: str = "") -> tuple[int, list[str]]:
    s, notes = 0, []
    b = info.get("boost", 0)
    if b >= 500:
        s += 35; notes.append(f"boost {b:.0f}")
    elif b >= 100:
        s += 20; notes.append(f"boost {b:.0f}")
    n_src = len(info.get("sources", ()))
    if n_src >= 2:
        s += 20; notes.append(f"in {n_src} lists")
    links = info.get("links", set())
    if "twitter" in links:
        s += 10
    if "telegram" in links:
        s += 10
    if "website" in links:
        s += 5
    if links:
        notes.append("socials: " + ",".join(sorted(links)))
    if mint in WATCHLIST or symbol.lower() in WATCHLIST:
        s += 30; notes.append("on your watchlist")
    return min(s, 100), notes
