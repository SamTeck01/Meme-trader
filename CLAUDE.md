# Meme Trader — project guide

AI-assisted Solana memecoin trading bot. Owner: SamTeck01 (Nigeria). Starting capital $20.
The full agreed plan is in `STRATEGY.md` — read it before changing anything.

## Rules
- Paper mode is the default. Live trading is an explicit config switch, only after the go-live test in STRATEGY.md §10 passes.
- Non-negotiable safety checks (mint/freeze authority revoked, sell test, no bundle >30%) are never bypassed, including the conviction lane.
- Risk limits live in code and the AI can never override them.
- Never commit secrets (private keys, API keys). Use env vars / server secrets; `.env` is gitignored.
- Budget: free data/AI only (no X API). Running cost target $0–5/month.
- Build in small steps; test each against live data in paper mode before moving on.

## Stack
Python worker (bot) · Supabase (DB + realtime) · Next.js dashboard on Vercel · Telegram bot · Groq/Gemini free LLM · Helius, Jupiter, DexScreener, pump.fun, RugCheck APIs.
