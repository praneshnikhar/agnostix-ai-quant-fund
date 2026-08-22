# Product Requirements Document (PRD)
## Agentic Trading Desk — AI Agents Performing Quant-Fund Workflows on Alpaca

**Version:** 0.1 (Hackathon Draft)
**Status:** Draft
**Owner:** [Team Name]
**Target Event:** Alpaca AI Trading Agents Hackathon

---

## 1. Vision

Build a multi-agent AI system that performs the core workflow of a small quantitative trading desk — research, signal generation, risk review, execution, and portfolio monitoring — operating on Alpaca's paper trading environment, with a human decision-maker kept in the loop at every trade.

The product is not "an AI that trades for you unsupervised." It is a **decision-support and execution pipeline** where agents do the research and drafting work a junior analyst or quant would do, and a human plays the role of portfolio manager who approves, rejects, or revises what the agents propose.

## 2. Problem Statement

Retail and small prop-trading teams don't have the headcount to run a full research → risk → execution pipeline the way an institutional quant fund does. Existing "AI trading bots" tend to fall into two bad extremes:

- **Fully autonomous black boxes** — no human oversight, no explainability, high blow-up risk.
- **Signal generators only** — an AI suggests ideas but there's no structured pipeline, risk enforcement, or audit trail connecting suggestion to execution.

There's a gap for a system that gives individuals/small teams an institutional-style workflow (multi-stage review, explicit risk gates, audit logs) powered by agents, without requiring them to build that infrastructure themselves.

## 3. Goals & Success Metrics

| Goal | Metric |
|---|---|
| Demonstrate a working multi-agent pipeline | End-to-end demo: data in → proposal → critic → human approval → order placed on Alpaca paper account |
| Show meaningful human-in-the-loop control | 100% of executed trades traceable to an explicit human approval event |
| Show risk discipline, not just signal generation | Critic agent blocks/flags proposals that violate configured risk limits, demonstrable in demo |
| Show explainability | Every agent decision has a stored natural-language rationale retrievable in the dashboard |
| (Stretch) Show learning over time | Agent proposal quality (approval rate, backtested Sharpe) improves across at least 2 iterations using logged human feedback |

## 4. Target Users

- **Primary (hackathon demo persona):** An individual trader / small prop-desk PM who wants AI-assisted idea generation but insists on final say over every trade.
- **Secondary (future):** Small RIAs or prop trading pods who want an auditable, explainable agent workflow rather than a black-box bot.

## 5. Scope

### In scope (hackathon MVP)
- Paper trading only, via Alpaca Trading API.
- Equities (and optionally crypto, since Alpaca supports 24/5) — single asset class to start.
- Agents: Data Agent, Research/Signal Agent(s), Critic Agent, Execution Agent, Portfolio Monitor Agent.
- Human approval gate (web dashboard) for every proposed trade.
- Dashboard: proposal queue, positions/P&L, agent reasoning log, kill switch.
- Basic backtesting harness for validating signal logic before it reaches the critic.

### Out of scope (for now)
- Real money / live trading.
- Options and multi-leg strategies (stretch goal only).
- Multi-account / multi-tenant support.
- Regulatory/compliance workflows beyond basic audit logging (Alpaca handles brokerage compliance).
- Fully autonomous execution without human approval (explicitly against the product philosophy).

## 6. Key User Stories

1. *As a PM*, I want to see a queue of AI-proposed trades with a clear thesis and risk assessment, so I can approve/reject quickly.
2. *As a PM*, I want to see why the critic agent flagged or passed a proposal, so I can trust or override it with reason.
3. *As a PM*, I want a single kill switch that halts all agent activity immediately, so I retain ultimate control.
4. *As a PM*, I want to see my current positions, P&L, and exposure at a glance.
5. *As a developer/researcher*, I want every proposal + human decision logged in a structured format, so I can use it later to improve agent behavior (RL/fine-tuning).
6. *As a judge/reviewer*, I want to see agent reasoning traces, not just outputs, so I can evaluate whether the system is doing real analysis.

## 7. Constraints & Assumptions

- All trading happens on Alpaca's **paper trading** environment — no real capital at risk.
- LLM cost/rate limits must be respected; agents should batch/cache data calls where possible.
- Market data may be delayed depending on Alpaca data plan tier used.
- Hackathon timeline is short (days, not weeks) — MVP must be achievable incrementally (see Development Plan).

## 8. Risks

| Risk | Mitigation |
|---|---|
| LLM hallucinated reasoning presented as fact | Critic agent cross-checks numeric claims against actual data before showing to human |
| Overfit/backtest-only "alpha" that fails live | Clearly label backtest vs. live performance in dashboard; don't oversell signal quality |
| Runaway agent loop placing excessive orders | Hard-coded rate limits + kill switch + human gate on every order |
| Demo fragility (API downtime, market closed) | Maintain a recorded demo / cached dataset fallback |

## 9. Out-of-the-Box Differentiators (for judging)

- Explicit **critic/generator separation** (the idea-generating agent never validates itself).
- Full **audit trail** from data → proposal → human decision → execution.
- Designed from day one to produce **RL-ready training data** (proposals + human labels) rather than bolting learning on later.
