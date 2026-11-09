# Meme Trader

AI-assisted Solana memecoin trading bot. Plan: [STRATEGY.md](STRATEGY.md). **Paper mode by default.**

## Status
- [x] Step 1: data clients (DexScreener, RugCheck, Jupiter) + safety filter
- [ ] Step 2: signal lanes (smart wallets, pump.fun, trending, hype)
- [ ] Step 3: AI judge (Groq)
- [x] Step 4: risk manager, fee budget, exits
- [x] Step 5: paper trading engine (+ Lane C trending/momentum)
- [ ] Step 6: Telegram bot
- [ ] Step 7: dashboard

## Run
```bash
pip install -r requirements.txt
python -m bot.scan --limit 15   # check live trending tokens against the safety filter
python -m bot.run              # paper trading loop (Ctrl+C to stop)
python -m pytest -q
```
