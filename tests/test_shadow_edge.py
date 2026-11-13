from bot import edge
from bot.shadow import Shadow, Obs


def mk(tmp_path):
    return Shadow(active=tmp_path / "a.json", done=tmp_path / "d.jsonl")


def test_stop_loss_sim(tmp_path):
    s = mk(tmp_path)
    s.observe("m", "X", "C", 1.0, {}, now=0)
    o = s.obs["m"]
    assert not s.update_one(o, 0.6, 50_000, 60)
    assert o.sim_left == 0 and abs(o.sim_out - 0.6) < 1e-9 and "stop" in o.sim_reason


def test_take_profit_then_trailing(tmp_path):
    s = mk(tmp_path)
    s.observe("m", "X", "C", 1.0, {}, now=0)
    o = s.obs["m"]
    s.update_one(o, 2.0, 50_000, 60)      # sell 50% at 2x -> 1.0
    s.update_one(o, 4.0, 50_000, 120)     # sell 25% at 4x -> +1.0
    s.update_one(o, 2.5, 50_000, 180)     # trailing stop (-35% from 4) -> 0.25*2.5
    assert o.sim_left == 0 and abs(o.sim_out - (1.0 + 1.0 + 0.625)) < 1e-6


def test_rug_and_horizons(tmp_path):
    s = mk(tmp_path)
    s.observe("m", "X", "C", 1.0, {"liquidity_usd": 50_000}, now=0)
    o = s.obs["m"]
    s.update_one(o, 0.9, 50_000, 400)
    assert o.marks == {"r5m": 0.9}
    assert s.update_one(o, 0.9, 100, 500)             # liquidity pulled
    assert o.sim_out == 0 and o.sim_reason == "rug" and o.marks["r6h"] == 0


def test_window_end_marks_to_market(tmp_path):
    s = mk(tmp_path)
    s.observe("m", "X", "C", 1.0, {}, now=0)
    o = s.obs["m"]
    assert s.update_one(o, 1.5, 50_000, 21600)
    assert abs(o.sim_out - 1.5) < 1e-9


def rows(lane, sim, n, **f):
    from datetime import datetime, timezone
    return [{"ts": datetime.now(timezone.utc).isoformat(), "lane": lane, "sim": sim, "rug": False,
             "features": {"rules_buy": True, **f}} for _ in range(n)]


def test_gate_blocks_losing_lane_only_with_evidence():
    assert edge.lane_allowed("C", rows("C", 0.8, 10))[0]          # too few samples
    assert not edge.lane_allowed("C", rows("C", 0.8, 50))[0]      # proven loser
    assert edge.lane_allowed("C", rows("C", 1.5, 50))[0]          # proven winner
    assert "OFF" in edge.report(rows("C", 0.8, 50))


def test_unknown_liquidity_is_not_a_rug(tmp_path):
    s = mk(tmp_path)
    s.observe("m", "X", "B", 1.0, {"liquidity_usd": 0}, now=0)
    assert not s.update_one(s.obs["m"], 1.1, 0, 60)
