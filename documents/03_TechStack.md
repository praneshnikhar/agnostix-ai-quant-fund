# Technology Stack Document
## Agentic Trading Desk

**Version:** 0.1

---

## 1. Guiding Principles

- Favor Python across the board — Alpaca SDKs, agent frameworks, and backtesting libraries are Python-first.
- Keep the Execution Agent as the *only* component with order-placing credentials — smallest possible blast radius.
- Prefer deterministic, code-enforced risk checks over LLM judgment wherever a hard rule can be written.
- Design the data model from day one so every agent action is loggable and replayable (feeds both debugging and future RL).

---

## 2. Core Stack

| Layer | Choice | Notes |
|---|---|---|
| Language (backend) | Python 3.11+ | Alpaca SDK, agent frameworks, data science stack |
| Trading/Brokerage | Alpaca Trading API + Alpaca MCP Server | Paper trading environment; MCP server lets agents call trading functions as structured tools |
| Market Data | Alpaca Market Data API (REST + WebSocket) | Bars, quotes, trades; add Alpaca News API for headlines |
| Agent Orchestration | LangGraph (or CrewAI as alternative) | Explicit state machine fits the propose→critique→approve→execute funnel well |
| LLM Provider | Claude (Sonnet for reasoning agents, Haiku for cheap/high-frequency tasks) | Use Claude's tool-calling for structured proposal/critic outputs |
| Backend API | FastAPI | Async, WebSocket support, easy to pair with Pydantic schemas |
| Database (relational) | PostgreSQL | Trades, proposals, approvals, users |
| Time-series store | TimescaleDB (Postgres extension) or plain Postgres with partitioning for hackathon speed | Bars/quotes cache |
| Task queue / scheduling | Celery + Redis, or APScheduler for hackathon simplicity | Periodic agent runs, order status polling |
| Frontend | Next.js (React) + TypeScript | SSR not essential but good DX; Vercel-deployable |
| Charts | TradingView Lightweight Charts (price/equity curves), Recharts (P&L, exposure breakdowns) | |
| Realtime UI updates | WebSocket (FastAPI native) or Socket.IO | Push proposal/portfolio updates to dashboard |
| Auth | Simple session auth (hackathon) → Auth0/Clerk if productionizing | Single-PM use case doesn't need heavy auth for MVP |
| Backtesting | vectorbt or backtrader | Validate signal logic against historical Alpaca bars before live/paper deployment |
| Deployment | Docker Compose locally; Railway/Render/Fly.io for hackathon demo hosting | Keep infra simple given time constraints |
| Observability | Structured JSON logging (structlog) + a simple `agent_events` table doubling as your audit log | Avoid heavy observability tooling for hackathon scope |

## 3. Agent Framework Choice Rationale

**LangGraph** is recommended over a fully custom loop because:
- The pipeline is naturally a directed graph with conditional edges (critic PASS → human gate; REJECT → log and stop).
- Built-in support for persistent state and human-in-the-loop interrupts (a node can pause execution pending external input — maps directly to the approval gate).
- Easier to visualize/debug the agent graph for demo purposes.

CrewAI is a reasonable alternative if the team prefers a "roles and tasks" mental model over explicit graph state; it's less natural for the interrupt-and-wait-for-human pattern.

## 4. MCP Integration

Use Alpaca's MCP server as the tool-calling layer for agents that need trading functions (account info, order placement, positions). This keeps agent code decoupled from raw REST calls and lets you swap in Claude, GPT, or others as the underlying reasoning model without rewriting tool integrations.

**Tool access should be scoped per agent:**
- Signal agents: market data + news tools only (read-only).
- Critic agent: market data tools (for verification) + risk-rule evaluation tool (custom, code-based).
- Execution agent: order placement tools only, gated by an internal "has valid human approval" check before the tool call is even attempted.

## 5. Environments

| Environment | Purpose |
|---|---|
| `dev` | Local development against Alpaca paper API with a small watchlist |
| `demo` | Stable, pre-seeded environment for the hackathon presentation (avoid live API flakiness during judging) |
| `backtest` | Offline, no live API calls — historical data replay for signal validation and (later) RL training |

## 6. Security Notes

- Alpaca API keys stored server-side only (env vars / secrets manager), never exposed to frontend.
- Execution Agent's credentials should ideally be scoped separately from data-reading credentials if Alpaca's key model allows it, so a compromised research agent can't place orders.
- Kill switch should be enforced at the API-gateway level (blocks execution endpoint entirely), not just as a UI state, so it can't be bypassed by a stuck agent loop.
