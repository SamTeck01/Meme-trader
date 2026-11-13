import time
from bot.lanes.wallets import WalletLane, parse_tx

W, M = "Wallet1", "MintX"


def tx(to=None, frm=None, mint=M, ts=None, sol=None):
    sol = sol if sol is not None else (-1e9 if to else 1e9)   # paid SOL on buy, got SOL on sell
    return {"signature": "s", "timestamp": ts or int(time.time()),
            "accountData": [{"account": W, "nativeBalanceChange": sol}],
            "tokenTransfers": [{"mint": mint, "tokenAmount": 5, "toUserAccount": to, "fromUserAccount": frm}]}


def test_parse_buy_sell():
    assert parse_tx(tx(to=W), W)[0].side == "BUY"
    assert parse_tx(tx(frm=W), W)[0].side == "SELL"
    assert parse_tx(tx(to=W, mint="So11111111111111111111111111111111111111112"), W) == []


def test_ingest_and_copy_exit():
    lane = WalletLane(wallets=[W], api_key="k")
    lane.ingest(parse_tx(tx(to=W), W))
    assert lane.candidates() == [(M, {W})]
    assert lane.candidates() == []           # consumed
    lane.ingest(parse_tx(tx(frm=W), W))
    assert lane.wallet_sold(W, M)


def test_stale_buy_ignored():
    lane = WalletLane(wallets=[W], api_key="k")
    lane.ingest(parse_tx(tx(to=W, ts=int(time.time()) - 3600), W))
    assert lane.candidates() == []


def test_airdrop_and_failed_tx_ignored():
    assert parse_tx(tx(to=W, sol=-5000), W) == []          # token in, only a fee paid = spam/airdrop
    assert parse_tx({**tx(to=W), "transactionError": {"e": 1}}, W) == []
