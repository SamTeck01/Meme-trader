# Meme Trader

AI-assisted Solana memecoin trading bot. Plan: [STRATEGY.md](STRATEGY.md). **Paper mode by default.**

## Status
- [x] Step 1: data clients (DexScreener, RugCheck, Jupiter) + safety filter
- [x] Step 2a: lanes B (pump.fun curve), C (trending momentum), D (hype/conviction)
- [x] Step 2b: lane A (smart-wallet copy, Helius polling + copy exit) — needs HELIUS_API_KEY + wallets
- [x] Step 3: AI judge (Groq → Gemini fallback, veto-only, every decision logged to `data/decisions.jsonl`)
- [x] Step 4: risk manager, fee budget, exits
- [x] Step 5: paper trading engine (+ Lane C trending/momentum)
- [x] Step 6: Telegram bot (alerts, daily summary, /status /positions /pnl /watch /unwatch /stop /start)
- [x] Step 6b: shadow tracker + edge report + evidence gate (STRATEGY.md v2 §3–4)
- [ ] Step 7: deploy 24/7, Supabase storage, dashboard

## Run
```bash
pip install -r requirements.txt
python -m bot.scan --limit 15   # check live trending tokens against the safety filter
python -m bot.run              # paper trading loop (Ctrl+C to stop)
python -m bot.edge             # edge report: which lanes/filters make money after costs
python -m pytest -q
```

## Environment variables
| Name | Needed for | Required |
|---|---|---|
| `PAPER_MODE` | `false` enables live trading (not built yet) | no (default paper) |
| `HELIUS_API_KEY` | lane A smart-wallet watching | later |
| `TELEGRAM_BOT_TOKEN` | alerts + commands | later |
| `TELEGRAM_CHAT_ID` | only this chat can control the bot (message the bot once; it replies with your id) | with Telegram |
| `WALLETS` | comma-separated smart wallets for lane A (or `config/wallets.txt`) | with Helius |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | AI judge | later |
| `ROUND_TRIP_COST_PCT` | cost assumed per trade in the edge report and gate (default 10) | no |
| `AROON_FILTER` | `false` turns the Aroon trend filter off (for A/B comparison) | no (default on) |
| `PUMPPORTAL_API_KEY` | optional: live pump.fun trade stream (key funded with ≥0.02 SOL). Without it, lane B polls DexScreener for free | no |
