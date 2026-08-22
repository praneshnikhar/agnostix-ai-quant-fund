# 15 — Monorepo Structure & Frontend Workspace Architecture

> **Status:** Repository / Product Structure Specification
> **Companion to:** `14_TechStack_Evolved.md`

---

## 1. Repository Layout — Monorepo

A monorepo is much better for Cline-driven development than a giant unstructured Python project.

```text
ai-quant-fund/
│
├── apps/
│   ├── web/                      # Next.js frontend
│   └── api/                      # FastAPI backend
│
├── packages/
│   ├── ui/                       # shared UI components / design system
│   ├── types/                    # shared TypeScript types / API contracts
│   └── config/                   # shared config (eslint, tsconfig, tailwind preset)
│
├── services/
│   ├── agents/                   # LangGraph agent definitions & graphs
│   ├── market-data/              # market data ingestion & normalization
│   ├── news/                     # news ingestion, extraction, sentiment
│   ├── execution/                # order construction & broker integration
│   ├── portfolio/                # positions, NAV, attribution
│   ├── risk/                     # deterministic risk engine
│   ├── backtesting/              # backtest & replay engine
│   ├── evaluation/               # outcome engine, scoring, calibration
│   └── model-gateway/            # provider-agnostic LLM gateway
│
├── research/
│   ├── notebooks/                # exploratory analysis
│   ├── experiments/              # tracked experiments
│   ├── datasets/                 # curated training datasets
│   └── models/                   # model artifacts
│
├── db/
│   ├── migrations/               # Alembic migrations
│   └── seeds/                    # seed data
│
├── infra/
│   ├── docker/                   # Dockerfiles
│   └── scripts/                  # operational scripts
│
├── docs/                         # this document series (01–18+)
│
├── tests/
│
├── .env.example
├── docker-compose.yml
├── Makefile
└── README.md
```

### Root Documentation Files (Cline workflow)

Create these at repo root so every Cline session starts from the same architectural context:

```text
AGENTS.md          # most important — see §3
ARCHITECTURE.md
DEVELOPMENT.md
DESIGN_SYSTEM.md
SECURITY.md
DECISIONS.md
CHANGELOG.md
```

---

## 2. Frontend Workspace Architecture

Structure the portal around **workspaces**, not just CRUD pages:

```text
/dashboard
    Overview

/markets
    Market Overview
    Watchlists
    Security Explorer

/research
    Research Feed
    Company Research
    News Intelligence

/agents
    Agent Floor
    Agent Detail
    Agent Performance

/signals
    Signal Feed
    Signal Detail

/committee
    Investment Committee
    Debate
    Decisions

/portfolio
    Portfolio
    Positions
    Performance
    Attribution

/risk
    Risk Dashboard
    Exposure
    Drawdown
    Stress Tests

/trading
    Orders
    Executions

/learning
    Model Performance
    Strategy Performance
    Training Runs
    Backtests
    Model Registry

/audit
    Event Log
    Decision Replay

/settings
```

That is the eventual product. We do not need to build all of it now — the shell and navigation should exist from M0 so each milestone fills in its workspace.

### Workspace ↔ Milestone Mapping

| Workspace | First populated at |
|---|---|
| /dashboard | M0 (shell) → M1 (data) |
| /markets | M1 |
| /research | M2 |
| /agents | M3 |
| /committee | M4 |
| /risk | M5 |
| /portfolio | M6 |
| /trading | M7 |
| /learning | M8 |
| /audit | M0 (event log) → M8 (decision replay) |

---

## 3. AGENTS.md — The Most Important File

`AGENTS.md` should tell Cline:

- Architecture rules
- Coding standards
- Security constraints
- Testing requirements
- UI rules
- Database rules
- Agent rules
- Prohibited shortcuts
- Definition of done

Every Cline session starts from this context. A draft skeleton:

```markdown
# AGENTS.md — Operating Rules for AI Coding Agents

## Architecture Rules
- Monorepo layout per docs/15_Monorepo_Structure.md. Never create top-level
  directories outside the defined structure.
- All LLM access goes through services/model-gateway. Never call OpenAI/
  Anthropic SDKs directly from agents.
- All market/news data access goes through the internal data interface.
  Never call external APIs from agents.
- Risk limits are deterministic Python code. Never implement risk checks
  in an LLM prompt.
- Strategy agents produce signals; only the PM/risk/execution chain
  produces orders.

## Coding Standards
- Backend: Python 3.12+, FastAPI, Pydantic v2, async-first, type hints
  everywhere, ruff + mypy clean.
- Frontend: TypeScript strict, Next.js App Router, shadcn/ui components,
  TanStack Query for server state, Zustand for local state.
- Shared types live in packages/types. Never duplicate API contracts.

## Database Rules
- PostgreSQL only. All schema changes via Alembic migrations.
- Every decision artifact is append-only (audit trail).
- Snapshots are immutable.

## Testing Requirements
- Every service has unit tests; every API endpoint has contract tests.
- No milestone is complete with failing tests.

## UI Rules
- Design system per DESIGN_SYSTEM.md. Dark institutional terminal theme.
- No generic SaaS card layouts, no neon crypto aesthetics.

## Prohibited Shortcuts
- No TODO comments left in merged code.
- No hardcoded API keys or secrets.
- No skipping migrations.
- No new dependencies without justification in DECISIONS.md.

## Definition of Done
- Code implemented, tests passing, lint clean, docs updated,
  CHANGELOG.md entry added, DECISIONS.md updated for architectural choices.
```

---

## 4. Infrastructure Discipline

For the first version, the full infrastructure is:

```text
Next.js → FastAPI → { PostgreSQL, Redis, Celery Workers → LangGraph → Agents/Risk/Execution }
```

Add heavier infrastructure (Kubernetes, Kafka, ClickHouse, Airflow, etc.) only with evidence of need.