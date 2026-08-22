# 17 — Milestone Roadmap: M0 → M10

> **Status:** Development Roadmap
> **Supersedes sequencing of:** `05_Development_Plan.md` (Phases 0–4 remain valid as MVP scope; this roadmap re-sequences for the full product)
> **Companion to:** `14_TechStack_Evolved.md`, `15_Monorepo_Structure.md`

---

## 1. Key Sequencing Decisions

### The first milestone is NOT trading

The first development milestone is:

## M0 — Foundation + Design System

Before implementing agents, establish: repository, architecture, database, API, frontend shell, design system, authentication foundation, logging, configuration, Docker, testing, CI, model gateway abstraction, and event architecture.

Then we build the actual fund.

### The UI is developed continuously

The original development plan puts the dashboard around Phase 3. For this larger product, the **design system and application shell move into M0**, so every backend capability immediately gets a proper visual representation.

---

## 2. Milestone Sequence

```text
M0  FOUNDATION
 │
 ▼
M1  MARKET INTELLIGENCE
 │
 ▼
M2  FUNDAMENTAL AI
 │
 ▼
M3  STRATEGY BAND
 │
 ▼
M4  INVESTMENT COMMITTEE
 │
 ▼
M5  QUANT RISK
 │
 ▼
M6  PORTFOLIO ENGINE
 │
 ▼
M7  PAPER EXECUTION
 │
 ▼
M8  LEARNING ENGINE
 │
 ▼
M9  META-ALLOCATOR
 │
 ▼
M10 PRODUCTION FUND PLATFORM
```

---

## 3. Milestone Details

### M0 — Foundation + Design System

Deliverables:

- Monorepo (`15_Monorepo_Structure.md`)
- Next.js application (shell, navigation, dark terminal theme)
- FastAPI application (health endpoint, config, structured logging)
- PostgreSQL (migrations) + Redis
- Docker Compose
- WebSocket infrastructure
- Typed API contracts (`packages/types`)
- Model gateway interface (abstraction only — no agent calls yet)
- Testing infrastructure, linting/formatting, CI
- Environment configuration, security baseline
- Root docs: AGENTS.md, ARCHITECTURE.md, DEVELOPMENT.md, DESIGN_SYSTEM.md, SECURITY.md, DECISIONS.md, CHANGELOG.md

Full spec: `18_M0_Specification_Cline_Prompt.md`

### M1 — Market Intelligence

First actual functional capability:

```text
Market data + News + Fundamentals + Company metadata
      ↓
Normalized data layer
      ↓
Market Snapshot
      ↓
Dashboard
```

At this point you can open `/markets/NVDA` and see: price, chart, volume, fundamentals, recent news, sentiment, technical indicators, market regime, recent agent observations.

**No trading yet.**

### M2 — First AI Analyst

Build **only** the Fundamental Analyst.

Input:

```text
Market Snapshot + Financial statements + Earnings + News
```

Output (all structured):

```text
Investment thesis
Evidence
Bull case
Bear case
Risks
Expected direction
Confidence
```

### M3 — Strategy Band

Add:

```text
Fundamental · Momentum · Mean Reversion · News · Macro
```

Each produces independent signals. The dashboard gets its first genuinely interesting screen: the **Agent Floor** — you can watch the agents work.

### M4 — Investment Committee

The first major "wow" milestone:

```text
                    NVDA

          ┌───────────┴───────────┐
          │                       │
       BULL CASE              BEAR CASE
          │                       │
      Fundamental             Valuation
      Momentum                Macro
      News                    Risk
          │                       │
          └───────────┬───────────┘
                      ▼
                AI JURY
                      ▼
              INVESTMENT THESIS
```

Then:

```text
BUY
Confidence: 82%
Suggested allocation: 2.4%
```

### M5 — Quant Risk Engine

**Non-LLM.** Hard rules:

```text
max_position
max_sector
max_drawdown
max_daily_loss
max_leverage
max_correlation
max_turnover
min_liquidity
```

The LLM can explain risk. It does not control risk.

### M6 — Portfolio Construction

```text
Signals → Expected returns → Risk model → Correlation
       → Portfolio optimizer → Target positions
```

This is where the system starts resembling a quant fund rather than an agent demo.

### M7 — Paper Execution

Connect Alpaca. The existing schema already separates proposal → human decision → order → execution result, which is exactly the right safety boundary.

Development flow:

```text
AI → Risk → Human approval → Paper order → Execution → Portfolio
```

No real capital initially.

### M8 — Learning System

```text
Every decision → Outcome → Evaluation → Agent performance
→ Strategy performance → Training dataset → Backtest
→ Walk-forward evaluation → Candidate model → Promotion
```

Builds on the RL approach in `06_RL_Improvement.md` rather than prematurely attempting live RL.

### M9 — Meta Allocator

Where it becomes genuinely differentiated. Instead of asking "which stock should we buy?", the system asks:

> **"Which intelligence should we trust right now?"**

```text
CURRENT REGIME
────────────────────
Strong trend
Low volatility
Risk-on
High liquidity

STRATEGY WEIGHTS
────────────────────
Momentum          34%
Fundamental       29%
News              18%
Macro             11%
Mean Reversion     8%
```

Eventually a contextual bandit / allocator.

### M10 — Production Fund Platform

Multi-portfolio, multi-user roles, compliance, live execution readiness — per Stage 4 of `13_Evolved_Architecture_Roadmap.md`.

---

## 4. Cline Working Method Per Milestone

Do not tell Cline "build my AI hedge fund" — that produces thousands of lines of loosely connected code. Work **milestone-by-milestone**.

For every milestone:

```text
1. Inspect
2. Plan
3. Implement
4. Test
5. Run
6. Review
7. Fix
8. Commit
9. Report
```

Cline should never silently skip architecture or tests.