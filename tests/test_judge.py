from bot.ai import judge


def test_parse_ok():
    v = judge.parse('sure: {"decision":"buy","confidence":82,"red_flags":["x"],"reason":"r"}')
    assert v.decision == "BUY" and v.confidence == 82 and v.buy


def test_parse_low_conf_not_buy():
    assert not judge.parse('{"decision":"BUY","confidence":65}').buy


def test_parse_garbage():
    assert judge.parse("no json") is None
    assert judge.parse('{"decision":"MAYBE","confidence":90}') is None


def test_no_keys_returns_none(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert judge.judge({"mint": "x"}) is None


def test_keys_but_failure_skips(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "dummy")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(judge, "_groq", lambda p, k: (_ for _ in ()).throw(judge.httpx.HTTPError("x")))
    v = judge.judge({"mint": "x"})
    assert v and not v.buy
