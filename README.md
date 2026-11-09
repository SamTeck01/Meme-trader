# Meme Trader

AI-assisted Solana memecoin trading bot. Plan: [STRATEGY.md](STRATEGY.md). **Paper mode by default.**

## Status
- [x] Step 1: data clients (DexScreener, RugCheck, Jupiter) + safety filter
- [x] Step 2a: lanes B (pump.fun curve), C (trending momentum), D (hype/conviction)
- [ ] Step 2b: lane A (smart-wallet copy) — needs HELIUS_API_KEY
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

## Environment variables
| Name | Needed for | Required |
|---|---|---|
| `PAPER_MODE` | `false` enables live trading (not built yet) | no (default paper) |
| `HELIUS_API_KEY` | lane A smart-wallet watching | later |
| `TELEGRAM_BOT_TOKEN` | alerts + commands | later |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | AI judge | later |
| `PUMPPORTAL_API_KEY` | optional: live pump.fun trade stream (key funded with ≥0.02 SOL). Without it, lane B polls DexScreener for free | no |
