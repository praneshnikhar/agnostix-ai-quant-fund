# Functional Requirements Document (FRD)
## Agentic Trading Desk

**Version:** 0.1
**Companion to:** 01_PRD.md, 03_TechStack.md, 04_Schemas.md

---

## 1. System Overview

The system is a pipeline of six functional modules:

`Data Ingestion → Research/Signal Agents → Critic Agent → Human Approval Gate → Execution Agent → Portfolio Monitor`

wrapped by a **Dashboard** (UI layer) and an **Audit/Logging** layer that touches every module.

---

## 2. Module: Data Ingestion Agent

| ID | Requirement |
|---|---|
| FR-1.1 | System shall pull real-time and historical bar data (OHLCV) from Alpaca Market Data API for a configurable watchlist. |
| FR-1.2 | System shall pull recent news headlines relevant to watchlist symbols (Alpaca News API or equivalent). |
| FR-1.3 | System shall normalize and cache incoming data in the time-series store to avoid redundant API calls within a configurable TTL. |
| FR-1.4 | System shall expose a clean internal data-access interface so downstream agents never call external APIs directly. |
| FR-1.5 | System shall flag stale/missing data and withhold signal generation for affected symbols rather than proceeding on incomplete data. |

## 3. Module: Research / Signal Agent(s)

| ID | Requirement |
|---|---|
| FR-2.1 | System shall generate trade proposals consisting of: symbol, direction (long/short), thesis (natural language), supporting quantitative signals used, proposed entry price/range, position size, stop-loss, take-profit, and confidence score. |
| FR-2.2 | Each proposal shall cite which data points (price action, news, fundamentals) informed the thesis, in a structured `evidence[]` field, not just prose. |
| FR-2.3 | System shall support running multiple independent signal agents (e.g., momentum agent, mean-reversion agent, news-sentiment agent) whose proposals are pooled. |
| FR-2.4 | Each proposal shall be persisted with a timestamp and unique proposal ID before being passed to the Critic. |
| FR-2.5 | Signal agents shall have no access to order-placement tools — read-only access to data and a "submit proposal" tool only. |

## 4. Module: Critic Agent

| ID | Requirement |
|---|---|
| FR-3.1 | Critic agent shall be a functionally and promptually separate agent from the proposing signal agent (no shared context/self-review). |
| FR-3.2 | Critic shall validate proposals against hard-coded risk rules: max position size (% of portfolio), max sector/symbol concentration, max daily loss budget remaining, max leverage. |
| FR-3.3 | Critic shall independently re-verify any numeric claim in the thesis against live data (e.g., "price is near 52-week low" must be checked, not trusted). |
| FR-3.4 | Critic output shall be one of: `PASS`, `PASS_WITH_WARNING`, `REJECT`, each with a structured reason. |
| FR-3.5 | Rejected proposals shall still be logged (not discarded) for later analysis of proposal quality. |
| FR-3.6 | Critic decisions shall be deterministic where possible (rule-based checks in code) and only use the LLM for qualitative assessment, to avoid non-reproducible risk gating. |

## 5. Module: Human Approval Gate

| ID | Requirement |
|---|---|
| FR-4.1 | Every proposal that receives `PASS` or `PASS_WITH_WARNING` from the Critic shall enter a pending-approval queue visible in the dashboard. |
| FR-4.2 | Human user shall be able to `APPROVE`, `REJECT`, or `REVISE` (edit size/entry/stop before approving) each proposal. |
| FR-4.3 | System shall require explicit secondary confirmation for proposals exceeding a configurable "large trade" threshold. |
| FR-4.4 | No order shall reach the Execution Agent without a corresponding `APPROVE` event tied to a specific human/session ID and timestamp. |
| FR-4.5 | System shall support a global **kill switch** that immediately halts all agent proposal generation and blocks any pending execution, overriding any in-flight approval. |
| FR-4.6 | All human decisions shall be persisted alongside the original proposal for future training-data use. |

## 6. Module: Execution Agent

| ID | Requirement |
|---|---|
| FR-5.1 | Execution agent shall place orders on Alpaca (paper) only for proposals with a valid `APPROVE` event. |
| FR-5.2 | Execution agent shall use the exact parameters (size, entry, stop, take-profit) from the approved (possibly human-revised) proposal — no silent modification. |
| FR-5.3 | Execution agent shall handle order rejections/partial fills from Alpaca gracefully and surface status back to the dashboard. |
| FR-5.4 | Execution agent shall attach stop-loss/take-profit as bracket orders where supported. |
| FR-5.5 | Execution agent shall log every order request/response verbatim for audit purposes. |

## 7. Module: Portfolio Monitor Agent

| ID | Requirement |
|---|---|
| FR-6.1 | System shall continuously sync open positions, cash, and P&L from Alpaca account state. |
| FR-6.2 | System shall compute and display portfolio-level risk metrics: total exposure, sector concentration, current drawdown, daily P&L. |
| FR-6.3 | System shall trigger an alert (and optionally auto-halt new proposals) if drawdown exceeds a configured threshold. |
| FR-6.4 | System shall track performance vs. a benchmark (e.g., SPY) over the session/demo period. |

## 8. Module: Dashboard (UI)

| ID | Requirement |
|---|---|
| FR-7.1 | Proposal Queue view: cards showing thesis, evidence, critic verdict, approve/reject/revise controls. |
| FR-7.2 | Portfolio view: positions table, equity curve, P&L, exposure breakdown. |
| FR-7.3 | Agent Reasoning Log: chronological, filterable trace of every agent action and rationale. |
| FR-7.4 | Kill switch control, prominently placed, with confirmation dialog. |
| FR-7.5 | Real-time updates via WebSocket (no manual refresh needed for price/position changes). |
| FR-7.6 | Historical view: past approved/rejected proposals with outcomes (for review and future RL use). |

## 9. Module: Audit & Logging

| ID | Requirement |
|---|---|
| FR-8.1 | Every state transition (proposal created → critic verdict → human decision → order placed → order filled) shall be recorded as an immutable event with timestamp. |
| FR-8.2 | Logs shall be queryable by symbol, agent, date range, and outcome. |
| FR-8.3 | System shall support exporting the full event log as structured data (JSON/CSV) for offline analysis or RL training.
