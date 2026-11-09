from bot.lanes.pumpfun import PumpLane, START_VSOL


def create(lane, dev_sol=0.5):
    lane.on_message({"txType": "create", "mint": "M", "symbol": "X", "traderPublicKey": "dev",
                     "solAmount": dev_sol, "vSolInBondingCurve": START_VSOL, "vTokensInBondingCurve": 1e9})


def trade(lane, kind, who, sol, vsol):
    lane.on_message({"txType": kind, "mint": "M", "traderPublicKey": who, "solAmount": sol,
                     "vSolInBondingCurve": vsol, "vTokensInBondingCurve": 5e8})


def test_emits_at_60pct_with_organic_buyers():
    lane = PumpLane(); create(lane)
    for i in range(30):
        trade(lane, "buy", f"w{i}", 1.7, START_VSOL + 1.7 * (i + 1))
    c = lane.candidates()
    assert len(c) == 1 and 0.5 <= c[0].progress <= 0.7
    trade(lane, "buy", "late", 0.1, START_VSOL + 55)
    assert lane.candidates() == []        # only once


def test_dev_sell_blocks():
    lane = PumpLane(); create(lane)
    trade(lane, "sell", "dev", 0.4, START_VSOL)
    for i in range(30):
        trade(lane, "buy", f"w{i}", 1.7, START_VSOL + 1.7 * (i + 1))
    assert lane.candidates() == []


def test_few_buyers_blocks():
    lane = PumpLane(); create(lane)
    for i in range(30):
        trade(lane, "buy", f"w{i % 5}", 1.7, START_VSOL + 1.7 * (i + 1))
    assert lane.candidates() == []


def test_big_dev_buy_blocks():
    lane = PumpLane(); create(lane, dev_sol=10)
    for i in range(30):
        trade(lane, "buy", f"w{i}", 1.7, START_VSOL + 1.7 * (i + 1))
    assert lane.candidates() == []


def test_free_mode_progress_from_market_cap():
    import math
    lane = PumpLane(); create(lane)
    t = lane.tokens["M"]
    # market cap that corresponds to vSol = 30 + 0.6*85 = 81
    vsol = START_VSOL + 0.6 * 85
    mcap_sol = 1e9 * vsol ** 2 / (30 * 1_073_000_000)
    pair = {"marketCap": mcap_sol * 150, "txns": {"h1": {"buys": 60, "sells": 20}}, "volume": {"h1": 5000}}
    lane.update_from_pair(t, pair, 150)
    assert math.isclose(t.progress, 0.6, rel_tol=1e-6)
    assert len(lane.candidates()) == 1
