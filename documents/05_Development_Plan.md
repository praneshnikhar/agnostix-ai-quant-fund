# Development Plan
## Agentic Trading Desk

**Version:** 0.1
Scoped for a short hackathon window with a "demo-first" MVP, then extensions if time allows.

---

## Phase 0 — Setup (Day 0)

- Alpaca paper account + API keys.
- Repo scaffold: `backend/` (FastAPI + agents), `frontend/` (Next.js), `infra/` (Docker Compose).
- Postgres running locally via Docker; apply schema from `04_Schemas.md`.
- Confirm Alpaca MCP server connectivity and basic tool calls (get account, get positions, place test paper order).
- Pick and lock the watchlist (5–10 liquid symbols — keeps data volume and LLM token usage manageable for a demo).

**Exit criteria:** Can manually place a paper trade via Alpaca API/MCP and see it reflected in your Postgres `orders`/`positions` tables.

---

## Phase 1 — Core Pipeline, No UI (Day 1)

- Data Ingestion Agent: pull bars + news for watchlist, cache in Postgres.
- One Signal Agent (start with a single strategy, e.g. momentum) producing `TradeProposal` JSON objects, persisted to `proposals`.
- Critic Agent: implement rule-based checks first (position size, concentration, drawdown budget) as plain code; add LLM qualitative layer second.
- Human Gate: CLI or simple script that lists pending proposals and accepts approve/reject input (UI comes in Phase 3 — don't block pipeline work on frontend).
- Execution Agent: on approval, place the paper order via Alpaca, log to `orders`.

**Exit criteria:** End-to-end flow works via terminal — data in, proposal out, human approves via CLI prompt, order lands on Alpaca paper account.

---

## Phase 2 — Multi-Agent + Portfolio Monitoring (Day 2)

- Add 1–2 more Signal Agents (mean-reversion, news-sentiment) so proposals are genuinely pooled from independent sources.
- Portfolio Monitor Agent: sync positions/equity, compute drawdown, daily P&L, exposure.
- Kill switch implemented at API level (blocks execution endpoint).
- Backtesting harness: run each signal agent's logic over historical data, log hypothetical performance — this becomes demo material ("here's what this strategy would have done").

**Exit criteria:** Multiple agents producing proposals concurrently; portfolio metrics visible via API; kill switch verified to actually stop execution.

---

## Phase 3 — Dashboard (Day 2–3, parallel to Phase 2 where possible)

- Proposal Queue view (cards, approve/reject/revise buttons wired to `/proposals/{id}/decision`).
- Portfolio view (positions table + equity curve chart).
- Agent Reasoning Log (chronological feed from `agent_events`).
- Kill switch button.
- WebSocket wiring for live updates.

**Exit criteria:** Full flow operable entirely from the UI, no CLI needed for the demo.

---

## Phase 4 — Polish & Demo Prep (Final day)

- Seed a "demo script" — a known sequence of proposals/approvals that reliably showcases the pipeline even if live market conditions are quiet or APIs are flaky.
- Record a backup demo video in case of live-demo failure.
- Write the one-pager / pitch: problem, architecture diagram, what's novel (critic/generator separation, full audit trail, RL-ready data).
- Clean up logging, add loading states, fix obvious UI rough edges.

---

## Stretch Goals (if time remains)

1. **RL feedback loop v0**: use logged `human_decisions` + outcome P&L to re-rank or re-weight signal agents (see companion doc `06_RL_Improvement.md`).
2. **Options/crypto expansion** beyond single-asset-class MVP.
3. **Explainability upgrade**: click into any proposal and see the exact data snapshot the agent reasoned over (full replayability).
4. **Multi-strategy allocation agent**: a meta-agent that weights how much "attention"/capital each signal agent gets based on recent track record.

---

## Suggested Team Split (if team of 3–4)

| Role | Focus |
|---|---|
| Agent/backend engineer | Signal + Critic + Execution agents, LangGraph orchestration |
| Data/infra engineer | Data ingestion, DB schema, Alpaca integration, backtesting harness |
| Frontend engineer | Dashboard, WebSocket wiring, UX of the approval flow |
| (If 4th) PM/quant-minded | Strategy logic for signal agents, risk rule design, demo narrative |
