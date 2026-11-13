# Meme Trader — AI Memecoin Trading Bot (Plan v2: evidence first)

Owner: Oyewole Abdul-Samad (Nigeria) · Chain: Solana · Starting capital: $20
Status: paper trading. Real money only after the go-live test (§10) passes.

## What changed in v2 and why
v1 assumed its signals (trending, hype, pump.fun, copy wallets) make money and planned to find
out from ~100 paper trades over two weeks. That is too slow and too little data, and nothing
showed any signal had an edge. Checking the top public "smart wallets" proved the point: the
best one by win rate was a token creator dumping on its own buyers within seconds.

v2 keeps the safety filter, risk limits and paper engine, and changes how trades are chosen:
1. **Measure everything.** Every token that passes the hard safety checks is followed for 6 hours,
   bought or not, and scored with our real exit rules (shadow tracker, §3). Hundreds of data points a day.
2. **Only proven signals trade.** A lane with 40+ tracked signals and a negative average after
   costs is switched off automatically. It keeps being tracked and switches back on if it recovers (§4).
3. **Filters must earn their place.** The edge report shows, for each filter (AI judge, Aroon,
   momentum, soft safety checks), whether tokens that pass do better than tokens that fail.
4. **Costs are part of the test.** Results are reported after a round-trip cost (default 10% of the
   position, `ROUND_TRIP_COST_PCT`). On a ~$3 position costs are the biggest enemy; the first tiny
   live trades calibrate this number.

## 0. Ground rules (agreed)
- It can lose money. It is not a money printer. Goal: find out if we have an edge, cheaply.
- Fully automatic trading (no per-trade approval).
- Budget: $0 for data/AI. No X API. Running cost target $0–5/month + trading fees.
- Paper trading first, on live data, before any real money.
- No rule in this file is bypassed because a signal "looks good". Evidence changes rules; hype does not.

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

## 3. Shadow tracker (the evidence engine)
- Every hard-safe token is recorded with its features (lane, momentum, hype, Aroon, liquidity,
  holder concentration, soft-check failures, AI verdict) and followed for 6 hours.
- Stored per token: price at 5 min / 15 min / 1 h / 6 h, high, low, rug flag (liquidity pulled or
  price gone), and the return our exit rules (§5) would have produced.
- `python -m bot.edge` or Telegram `/report` prints the edge report: results by lane and a
  yes/no comparison for every filter.

## 4. Evidence gate and AI judge
- Gate: lane needs ≥ 40 rule-approved signals in the last 7 days before it can be judged;
  negative average after costs → lane off (still tracked). Lives in code; the AI cannot override it.
- AI judge: Groq free tier, Gemini fallback. Runs only after safety + rules + gate say yes.
  Strict JSON `{decision, confidence, red_flags, reason}`; buys only at confidence ≥ 70; veto-only.
- The AI is itself on trial: the report compares "AI said BUY" against "AI said SKIP". If it does
  not help, it is removed.
- Lane A (copy wallets) candidates must show ≥ 5 round trips with median hold ≥ 10 minutes and must
  not be the creator of the tokens they trade. Public leaderboards are a starting list, not proof.

## 5. Position sizing & exits
| Rule | Normal | Conviction (hype) |
|---|---|---|
| Size | 15% of balance (~$3) | up to 30% |
| Stop-loss | −30% | −40% |
| Min token age | lane-specific | can skip |
| Max open | 4 total | 1 conviction at a time |

Take-profit: sell 50% at 2x, 25% at 4x, last 25% on −35% trailing stop.
Copy exit: if the copied wallet sells, we sell. Time stop: flat after 6 h → close.

## 5b. Account-level protection
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
Alerts on every buy/sell + daily summary. Commands: `/report`, `/status`, `/stop`, `/start`, `/watch <ticker|CA|account>`, `/unwatch`, `/positions`, `/pnl`.

## 9. Dashboard (phone-friendly web app)
Home (balance, today P&L, trades counter, balance chart) · Positions · AI feed (every token reviewed + reason) · Wallets (followed wallets + performance) · Settings (paper/live, risk limits, kill switch, deposit QR, withdraw).

## 10. Go-live test (paper → real)
Run ≥ 2 weeks, ≥ 100 paper trades and ≥ 500 shadow observations. Go live only if:
- At least one lane shows a positive average after costs in the edge report over ≥ 100 signals
- Paper account profitable after fees and slippage
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
Done: data clients, safety filter, lanes A–D, risk manager, paper engine, AI judge, Telegram,
shadow tracker, edge report, evidence gate.
Next: 1) deploy worker 24/7 · 2) Supabase storage (replaces local files) · 3) dashboard ·
4) first weekly edge review → cut or tune lanes · 5) go-live test → live with $20.

## 13. Accounts the owner needs (free)
- GitHub: empty repo (e.g. `meme-trader`)
- Groq (console.groq.com) and/or Google AI Studio
- Helius (helius.dev)
- Supabase (already connected)
- Telegram: create bot via @BotFather
- Keys are entered through a secure form — never pasted in chat.
