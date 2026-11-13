# Meme Trader — project guide

AI-assisted Solana memecoin trading bot. Owner: SamTeck01 (Nigeria). Starting capital $20.
The agreed plan is `STRATEGY.md` (v2, evidence first) — read it before changing anything.
The owner is not a programmer: explain in plain language, lead with what works and what is blocked.

## Rules
- Paper mode is the default. Live trading is an explicit config switch, only after the go-live test in STRATEGY.md §10 passes. Live trading is not built yet (`bot/run.py` exits if `PAPER_MODE=false`).
- Non-negotiable safety checks (mint/freeze authority revoked, sell test, no bundle >30%) are never bypassed, including the conviction lane.
- Risk limits and the evidence gate live in code and the AI can never override them.
- Never commit secrets (private keys, API keys). Use env vars / server secrets; `.env` is gitignored. Never print key values.
- Budget: free data/AI only (no X API). Running cost target $0–5/month.
- Build in small steps; test each against live data in paper mode before moving on.
- If the owner asks to skip a rule because a signal "looks good" (e.g. follow a hot wallet), check the data first and say plainly what it shows.

## Stack
Python worker (bot) · Supabase (DB + realtime, not wired yet) · Next.js dashboard on Vercel (not built) · Telegram bot · Groq/Gemini free LLM · Helius, Jupiter, DexScreener, GeckoTerminal, pump.fun, RugCheck APIs.

## Where things are
| File | What it does |
|---|---|
| `bot/run.py` | Main paper loop: gather candidates → safety → rules → evidence gate → AI judge → risk → paper buy; exits; Telegram commands |
| `bot/safety.py` | Hard + soft safety checks (RugCheck, DexScreener, Jupiter sell test) |
| `bot/risk.py`, `bot/config.py` | Position sizing, stops, take-profits, daily limits; all numbers |
| `bot/paper.py` | Paper broker (state in `data/paper_state.json`) |
| `bot/shadow.py` | Follows every hard-safe token for 6h and scores it with the real exit rules |
| `bot/edge.py` | Edge report (`python -m bot.edge`, Telegram `/report`) and the lane on/off gate |
| `bot/ai/judge.py` | Groq → Gemini judge, veto-only, confidence ≥ 70; no key = no-AI baseline |
| `bot/lanes/` | `wallets.py` lane A (Helius polling, trades detected by money flow), `pumpfun.py` lane B, `hype.py` lane D; lane C momentum is `bot/momentum.py` + `bot/aroon.py` |
| `bot/telegram.py` | Long polling, obeys only `TELEGRAM_CHAT_ID` |
| `data/` (gitignored) | Local state: paper account, shadow observations, decision log |

Run: `pip install -r requirements.txt` · `python -m pytest -q` (50 tests) · `python -m bot.run --cycles 1` (one live paper cycle, ~2 min) · `python -m bot.edge`.
Gotcha: `.gitignore` must say `/data/`, not `data/` — the latter hides `bot/data/`.

## Current state (updated 2026-11-13)
Work is on branch `ccr-55b22fb4-aatt3q` (not merged to the default branch; no pull request yet).

Working, tested on live data in paper mode: lanes B, C, D, safety filter, risk manager, paper broker, shadow tracker, edge report, evidence gate, Telegram code.
Built but never run with real inputs: AI judge (no `GROQ_API_KEY`/`GEMINI_API_KEY` set), lane A end to end (key works, no wallets chosen), Telegram alerts (no `TELEGRAM_CHAT_ID`).
No evidence yet that any lane makes money: the bot has only run for minutes at a time.

Environment variables set in the cloud environment: `HELIUS_API_KEY`, `TELEGRAM_BOT_TOKEN` (bot username `SamTeck_Meme_Bot`).
Missing: `TELEGRAM_CHAT_ID` (owner must press Start in the bot, then read the numeric id from `getUpdates`), `GROQ_API_KEY`, `WALLETS`.

Wallet research so far: GMGN blocks automated access (Cloudflare). KolScan's leaderboard (49 wallets) had none that qualify under STRATEGY.md §4. "Wugi" (862TYSv…) has a 73% win rate but is a pump.fun token creator who dumps within ~10 seconds of launch — do not follow. "Sheep" (78N177f…) trades in a copyable style (median hold ~2h) but wins only 52%; the owner has not decided whether to add it.

## Next steps, in order
1. Deploy the worker 24/7 (Railway or a $5 VPS; owner has not chosen). Until this happens there is no data.
2. Move local `data/` files to Supabase (schema not created yet) so state survives restarts and the dashboard can read it.
3. After a few days of running: first edge report review; cut or tune lanes; calibrate `ROUND_TRIP_COST_PCT` (10% is an untested estimate).
4. Dashboard (Next.js on Vercel), STRATEGY.md §9.
5. Nightly AI review of the day's trades (STRATEGY.md §4), not built.
6. Live broker (Jupiter swaps) only after the §10 go-live test passes.
