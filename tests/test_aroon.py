from bot import aroon


def bars(closes):
    return [[i, c, c * 1.01, c * 0.99, c, 1] for i, c in enumerate(closes)]


def test_uptrend():
    up, down, osc = aroon.aroon(*zip(*[(c * 1.01, c * 0.99) for c in range(1, 20)]))
    assert up == 100 and osc > 0


def test_downtrend_blocks():
    s, note, blocked = aroon.adjust(70, bars(list(range(30, 10, -1))))
    assert blocked and "downtrend" in note


def test_uptrend_bonus():
    s, _, blocked = aroon.adjust(50, bars(list(range(10, 30))))
    assert s == 65 and not blocked


def test_choppy_penalty():
    closes = [10, 12] * 10
    s, note, blocked = aroon.adjust(60, bars(closes))
    assert not blocked and s <= 60


def test_too_few_candles_neutral():
    assert aroon.adjust(60, bars([1, 2, 3])) == (60, "aroon n/a (too few candles)", False)
