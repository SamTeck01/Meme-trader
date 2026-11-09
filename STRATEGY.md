# Meme Trader — AI Memecoin Trading Bot (Plan v1)

Owner: Oyewole Abdul-Samad (Nigeria) · Chain: Solana · Starting capital: $20
Status: planning complete → ready to build. Real money only after paper test passes.

## 0. Ground rules (agreed)
- It can lose money. It is not a money printer. Goal: find out if we have an edge, cheaply.
- Fully automatic trading (no per-trade approval). Fast: continuous scanning, many trades.
- Budget: $0 for data/AI. No X API. Running cost target $0–5/month + trading fees.
- Paper trading first, on live data, before any real money.

## 1. Signal sources (all free)
| Lane | Source | What triggers a look |
|---|---|---|
| A. Smart-wallet copy | Helius webhooks on 5–7 selected wallets (GMGN Smart Money / KolScan to pick them: >60% win rate, 30+ trades, 7+ days history, no 10-second flip patterns) | A tracked wallet buys |
| B. Early pump.fun | pump.fun new/trending/about-to-graduate | Bonding curve 50–70% full + creator wallet with clean/good history |
| C. Trending | DexScreener trending + boosts | Rising volume, buys > sells |
| D. Hype / conviction | DexScreener boosts, pump.fun trending, creator track record, multiple smart wallets in, token's own X/TG links (checked by opening the page), user `/watch` list, optional: reading Telegram call groups via user's own account | High hype score |

## 2. Safety filter (code, instant, every token)
Non-negotiable (even conviction trades):
- Mint authority and freeze authority revoked
- Test sell succeeds (not a honeypot)
- No wallet cluster/bundle holding >30%

Standard (conviction lane may skip):
- Top 10 holders <30% (excluding pool/curve); creator <5%; creator has no rug history
- Enough liquidity to exit a position
- Not already up >10x today

## 3. AI judge
- Model: Groq free tier (fast, ~1–2 s). Fallback: Gemini free tier. Optional paid upgrade (Claude/Grok) only if A/B test shows better calls.
- Input: signal, token numbers, name/description, social links + account age/followers, smart wallets holding, creator history.
- Output (strict JSON): `{decision: BUY|SKIP, confidence: 0-100, red_flags: [], reason: ""}`
- Buys only at confidence ≥ 70. Model is swappable.
- Nightly review: AI reads the day's trades and *suggests* rule changes; owner approves.

## 4. Position sizing & exits
| Rule | Normal | Conviction (hype) |
|---|---|---|
| Size | 15% of balance (~$3) | up to 30% |
| Stop-loss | −30% | −40% |
| Min token age | lane-specific | can skip |
| Max open | 4 total | 1 conviction at a time |

Take-profit: sell 50% at 2x, 25% at 4x, last 25% on −35% trailing stop.
Copy exit: if the copied wallet sells, we sell. Time stop: flat after 6 h → close.

## 5. Account-level protection
- Daily stop: −25% day → pause until next day.
- Conviction lane: 2 losses in a row → lane paused for the day.
- Hard floor: balance < $8 → stop everything, Telegram alert.
- Daily fee budget: 10% of balance (~$2 at start), spent on best signals first. Limits scale up as balance grows.
- Fees tracked separately (AI P&L vs fees paid).

## 6. Execution
- Swaps via Jupiter API; pump.fun curve trades via pump.fun/PumpPortal-style API.
- Slippage cap per trade; low priority fee (tuned to spend within fee budget).
- Paper mode simulates fills with realistic slippage (3–10%) and fees.

## 7. Money flow & security
- Fund: naira → USDT on Bybit P2P or Quidax/Busha (SEC-licensed) → SOL → bot wallet (address + QR on dashboard). Keep ~0.05 SOL for fees.
- Bot wallet: brand-new, dedicated, only holds trading money.
- Private key: encrypted server secret. Never in code or chat.
- Withdraw button: sends only to one pre-set owner address.
- Kill switch: dashboard + Telegram `/stop` → sell all to SOL, halt.
- Keep trade logs (Nigeria Tax Act 2025 treats crypto gains as income).

## 8. Telegram bot
Alerts on every buy/sell + daily summary. Commands: `/status`, `/stop`, `/start`, `/watch <ticker|CA|account>`, `/unwatch`, `/positions`, `/pnl`.

## 9. Dashboard (phone-friendly web app)
Home (balance, today P&L, trades counter, balance chart) · Positions · AI feed (every token reviewed + reason) · Wallets (followed wallets + performance) · Settings (paper/live, risk limits, kill switch, deposit QR, withdraw).

## 10. Go-live test (paper → real)
Run ≥ 2 weeks and ≥ 100 trades. Go live only if:
- Profitable after fees and slippage
- No day worse than −25%
- Rugs < 10% of trades
- Beats a "no-AI" baseline (buy everything that passes the safety filter)

## 11. Stack & cost
| Part | Tool | $/month |
|---|---|---|
| Bot worker 24/7 | Python on Railway / $5 VPS | 0–5 |
| Chain data + wallet watch | Helius free | 0 |
| Token data | DexScreener, RugCheck, pump.fun, Jupiter | 0 |
| AI | Groq / Gemini free | 0 |
| Database + realtime | Supabase free | 0 |
| Dashboard | Next.js on Vercel free | 0 |
| Trading fees | priority fees | ~$0.10–0.50/trade |

## 12. Build order
1. Repo setup, config, Supabase schema
2. Token data + safety filter (log what passes; check a week later how many rugged)
3. Signal lanes A–D
4. AI judge
5. Risk manager + fee budget + exits
6. Paper trading engine
7. Telegram bot
8. Dashboard
9. Paper run (2+ weeks) → review → live with $20
10. Strategy Lab (see §14)

## 14. Strategy Lab (step 10 — after the bot runs)
Automated research loop, inspired by agentic research pipelines: find ideas → turn into testable rules → backtest → paper → keep only winners.
1. **Collect ideas** from GitHub repos, arXiv papers, web articles/X threads found via search, and tutorial transcripts the owner sends in (YouTube blocks cloud servers, so transcripts come via the owner: paste the YouTube "Show transcript" text, or upload the video file).
2. **Extract** each idea into a structured rule (AI, free model): entry condition, exit condition, filters, which lane it fits.
3. **Generate variants** (thresholds, timeframes) — capped per idea to limit overfitting.
4. **Backtest** on our own stored history: the bot logs every candidate token, its safety/momentum/Aroon readings and later prices from day one (`data/history`).
5. **Promote** only if: ≥100 backtest trades, positive after fees+slippage, beats current live rules, holds up on a held-out time period. Then 2 weeks of paper trading before it can touch real money.
6. **Report**: nightly summary (ideas found, variants tested, promoted/rejected, AI cost) to Telegram and dashboard. AI budget cap: $0.50/day (free models first).

## 13. Accounts the owner needs (free)
- GitHub: empty repo (e.g. `meme-trader`)
- Groq (console.groq.com) and/or Google AI Studio
- Helius (helius.dev)
- Supabase (already connected)
- Telegram: create bot via @BotFather
- Keys are entered through a secure form — never pasted in chat.
