# Agnostix — Autonomous Options Desk (Hackathon Write-up)

**One-page write-up covering AI logic, risk gates, and Alpaca infrastructure.**

## What it is

Agnostix is an autonomous options-trading agent on Alpaca paper. Its core idea
is a hard architectural rule: **the LLM is the least-trusted component**. It
proposes a direction and a thesis — nothing more. Every number that can lose
money (strike, size, strategy, risk decision, execution) is computed by
deterministic code that can — and often does — refuse the model.

## AI logic

1. **Signal (LLM).** A provider-agnostic Model Gateway (OpenRouter / OpenAI /
   Anthropic / Ollama / any OpenAI-compatible endpoint) prompts a single
   bounded question: *bullish, bearish, neutral, or abstain — and how
   confident?* The model returns structured JSON (`SignalOutput`): direction,
   confidence, thesis, catalyst, invalidation. No strike, no quantity, no
   strategy. Below a confidence floor (0.55) the agent abstains.
2. **Strategy (deterministic code).** Given the direction, the strategy
   builder picks every strike and width from the live option chain — always a
   *defined-risk* structure: bull put spread, bear call spread, iron condor,
   or cash-secured put. Max loss is finite and pre-computed.
3. **Sizing (deterministic code).** Contract count is capped so per-trade
   max loss stays under the risk budget; the model never sizes.
4. **Journal (deterministic).** Every decision, refusal, and order is appended
   to a SHA-256 hash-chained ledger. Tampering with any entry breaks the chain.

## Risk gates (deterministic-only, an LLM never participates)

Ten pure-math gates run on every proposal; any *hard* failure refuses, *soft*
failures reduce:

| Gate | Type | Effect |
|---|---|---|
| Defined risk | hard | no finite max loss → refuse |
| Max loss / trade | hard | 2% of equity |
| Max total defined risk | hard | 25% of equity |
| Concentration | hard | 10% per underlying |
| IV/vol rank band | soft | outside [0.20, 0.95] → reduce |
| DTE window | hard | 7–45 days |
| Probability of profit | soft | ≥ 0.60 |
| Daily-loss circuit breaker | hard | halt desk at −3% daily |
| Open-positions limit | hard | < 10 |
| Cash collateral | hard | cash ≥ max loss |

A kill switch halts the whole desk; the WebSocket broadcasts it live.

## Alpaca infrastructure

- **Trading API** (`alpaca-py`, paper): option contracts, option snapshots
  (bid/ask + broker Greeks), multi-leg `OrderClass.MLEG` orders for spreads,
  single-leg orders, account/equity (`last_equity` for daily P&L).
- **Market Data API**: historical bars → realized-vol / vol-rank proxy for the
  IV-rank gate.
- **MCP**: `services/execution/mcp_boundary.py` is the Alpaca MCP integration
  boundary (`ALPACA_MCP_URL`), with the SDK/API adapter as the durable
  fallback — the domain never depends on MCP.
- **CLI**: `python -m infra.scripts.agnostix` exposes status / chain / decide /
  run / journal --verify / kill with structured JSON output.
- **Paper only**: `ALPACA_PAPER=false` is hard-refused at construction.

## Interactive demo (what judges can play with)

- **War Room** (`/trading`): live equity curve, account, open strategies,
  hash-chained journal, kill switch, one-click "run cycle".
- **Playground** (`/playground`): type a symbol + inject a "what-if" scenario
  (earnings miss, IV crush, Fed hike) and watch the agent reason **live** —
  market context → signal → strategy → every risk gate → verdict — streamed
  over SSE. Dry-run by default.
- **Options chain** (`GET /options/chain/{symbol}`): live Greeks-enriched chain.
