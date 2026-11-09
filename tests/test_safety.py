from bot.safety import SafetyInputs, evaluate

SUPPLY = 1_000_000


def report(**kw):
    r = {
        "token": {"supply": SUPPLY, "decimals": 6, "mintAuthority": None, "freezeAuthority": None},
        "topHolders": [{"owner": f"w{i}", "address": f"a{i}", "pct": 2.0} for i in range(10)],
        "knownAccounts": {}, "insiderNetworks": [], "creatorBalance": 0, "risks": [], "rugged": False,
    }
    r.update(kw)
    return r


PAIR = {"liquidity": {"usd": 50_000}, "priceChange": {"h24": 20}}
QUOTE = {"outAmount": "123", "priceImpactPct": "0.01"}


def run(conviction=False, **kw):
    inp = SafetyInputs(mint="M", report=kw.pop("rep", report()), pair=kw.pop("pair", PAIR),
                       sell_quote=kw.pop("quote", QUOTE))
    return evaluate(inp, conviction=conviction)


def test_clean_token_passes():
    assert run().passed


def test_mint_authority_is_hard_fail_even_for_conviction():
    rep = report(token={"supply": SUPPLY, "decimals": 6, "mintAuthority": "X", "freezeAuthority": None})
    assert not run(rep=rep, conviction=True).passed


def test_freeze_authority_hard_fail():
    rep = report(token={"supply": SUPPLY, "decimals": 6, "mintAuthority": None, "freezeAuthority": "X"})
    assert not run(rep=rep).passed


def test_no_sell_route_is_hard_fail():
    assert not run(quote=None, conviction=True).passed


def test_bundle_cluster_hard_fail():
    rep = report(insiderNetworks=[{"currentHolding": SUPPLY * 0.4}])
    res = run(rep=rep, conviction=True)
    assert not res.passed and any("cluster" in f for f in res.hard_fails)


def test_concentrated_holders_soft_fail_but_conviction_allowed():
    rep = report(topHolders=[{"owner": "w", "address": "a", "pct": 50.0}])
    assert not run(rep=rep).passed
    assert run(rep=rep, conviction=True).passed


def test_pool_accounts_excluded_from_top10():
    rep = report(topHolders=[{"owner": "pool", "address": "p", "pct": 60.0}],
                 knownAccounts={"pool": {"type": "AMM"}})
    assert run(rep=rep).passed


def test_low_liquidity_soft_fail():
    assert not run(pair={"liquidity": {"usd": 500}, "priceChange": {"h24": 0}}).passed


def test_missing_report_fails():
    assert not run(rep=None, conviction=True).passed
