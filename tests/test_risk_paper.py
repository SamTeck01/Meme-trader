import random
from datetime import datetime, timedelta, timezone

from bot.paper import PaperBroker
from bot.risk import DayState, Position, RiskManager

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def pos(conviction=False, entry=1.0):
    return Position("M", "T", "A", conviction, entry, 100, 100, 100, NOW, peak_price=entry)


def test_stop_loss():
    a = RiskManager().check_exit(pos(), 0.69, NOW)
    assert a and a.fraction == 1.0 and "stop" in a.reason


def test_conviction_wider_stop():
    rm = RiskManager()
    assert rm.check_exit(pos(conviction=True), 0.65, NOW) is None
    assert rm.check_exit(pos(conviction=True), 0.59, NOW).fraction == 1.0


def test_take_profit_ladder_and_trailing():
    rm, p = RiskManager(), pos()
    assert rm.check_exit(p, 2.0, NOW).fraction == 0.5
    assert rm.check_exit(p, 3.0, NOW) is None
    assert rm.check_exit(p, 4.0, NOW).fraction == 0.5      # 25% of original = half of remaining
    assert rm.check_exit(p, 6.0, NOW) is None              # new peak
    assert "trailing" in rm.check_exit(p, 3.8, NOW).reason


def test_time_stop_only_when_flat():
    rm = RiskManager()
    later = NOW + timedelta(hours=7)
    assert "time" in rm.check_exit(pos(), 1.05, later).reason
    assert rm.check_exit(pos(), 1.5, later) is None


def test_copy_exit():
    assert "copied" in RiskManager().check_exit(pos(), 1.1, NOW, copied_wallet_sold=True).reason


def test_entry_limits():
    rm, day = RiskManager(), DayState("d", 20)
    assert rm.can_open(20, 20, [], day, False)[0]
    assert not rm.can_open(20, 20, [pos()] * 4, day, False)[0]
    assert not rm.can_open(20, 20, [pos(conviction=True)], day, True)[0]
    assert not rm.can_open(14, 14.9, [], day, False)[0] and day.halted   # -25% day


def test_hard_floor_kills():
    rm = RiskManager()
    assert not rm.can_open(7, 7.9, [], DayState("d", 8.5), False)[0]
    assert rm.killed


def test_fee_budget():
    day = DayState("d", 20, fees_spent=1.8)
    assert not RiskManager().can_open(20, 20, [], day, False)[0]


def test_conviction_streak_pause():
    rm, day = RiskManager(), DayState("d", 20)
    rm.record_close(pos(True), -1, day)
    rm.record_close(pos(True), -1, day)
    assert day.conviction_paused


def test_paper_round_trip_with_costs(tmp_path):
    b = PaperBroker(20, state_file=tmp_path / "s.json", rng=random.Random(1))
    b.buy("M", "T", 3, 1.0, "A")
    assert b.cash < 17
    b.sell("M", 1.0, 1.0, "test")
    assert "M" not in b.positions
    assert b.cash < 20            # flat price still loses to slippage + fees
    b2 = PaperBroker(20, state_file=tmp_path / "s.json")
    assert abs(b2.cash - b.cash) < 1e-9 and len(b2.trades) == 2
