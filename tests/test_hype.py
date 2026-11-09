from bot.lanes import hype


def test_strong_hype():
    info = {"boost": 500, "sources": {"a", "b"}, "links": {"twitter", "telegram", "website"}}
    s, _ = hype.hype_score(info)
    assert s >= 70


def test_watchlist_boosts():
    hype.WATCHLIST.add("jeff")
    s, notes = hype.hype_score({"boost": 0, "sources": {"a"}, "links": set()}, symbol="JEFF")
    assert s == 30 and "watchlist" in notes[-1]
    hype.WATCHLIST.clear()
