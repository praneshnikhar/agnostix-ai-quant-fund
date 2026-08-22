# 18 — M0 Implementation Specification & Cline Prompt

> **Status:** Implementation Specification (M0 — Foundation + Design System)
> **Companion to:** `17_Milestone_Roadmap_M0_M10.md`
> **Rule:** Do not start coding agents yet. The first Cline task is M0 Foundation only.

---

## 1. M0 Objective

Produce a working repository with:

```text
✓ Monorepo
✓ Next.js application
✓ FastAPI application
✓ PostgreSQL
✓ Redis
✓ Docker Compose
✓ Database migrations
✓ API health endpoint
✓ Frontend shell
✓ Design system foundation
✓ Dark trading-terminal theme
✓ Sidebar/navigation
✓ Dashboard shell
✓ WebSocket infrastructure
✓ Typed API contracts
✓ Model gateway interface
✓ Structured logging
✓ Testing infrastructure
✓ Linting/formatting
✓ Environment configuration
✓ Security baseline
✓ Documentation
```

Then we inspect what Cline produced before moving to M1.

---

## 2. M0 Detailed Requirements

### 2.1 Repository

- Monorepo per `15_Monorepo_Structure.md` (apps/, packages/, services/, research/, db/, infra/, docs/, tests/)
- Root files: `.env.example`, `docker-compose.yml`, `Makefile`, `README.md`
- Root docs: `AGENTS.md`, `ARCHITECTURE.md`, `DEVELOPMENT.md`, `DESIGN_SYSTEM.md`, `SECURITY.md`, `DECISIONS.md`, `CHANGELOG.md`

### 2.2 Backend (apps/api — FastAPI, Python 3.12+)

- App factory pattern; settings via pydantic-settings loaded from environment
- `GET /health` endpoint returning app version, db status, redis status
- Structured JSON logging (request id, level, timestamp)
- CORS configured for the web app origin
- WebSocket endpoint `/ws` with connection manager and heartbeat (broadcast stub)
- Alembic migrations wired to PostgreSQL; initial migration creates an `events` table (append-only audit/event log)
- Async SQLAlchemy (or equivalent) session management
- Model gateway **interface only**: `services/model-gateway` with `ModelGateway` abstract interface, provider stubs (anthropic/openai/ollama), routing skeleton, telemetry schema — no real API calls in M0
- Celery app configured with Redis broker; one example task (e.g., `ping`) proving worker round-trip
- Tests: pytest + pytest-asyncio; health endpoint test, gateway interface test, one Celery task test

### 2.3 Frontend (apps/web — Next.js App Router, TypeScript strict)

- Workspace route skeleton per `15_Monorepo_Structure.md` §2: /dashboard, /markets, /research, /agents, /signals, /committee, /portfolio, /risk, /trading, /learning, /audit, /settings — each a placeholder page with correct metadata
- Layout: sidebar navigation (workspace routes, collapsible), topbar (market status dot, clock), content area
- Dark trading-terminal theme per `16_Design_System_Direction.md`: graphite background, near-black panels, restrained borders, tabular numerals, semantic status colors
- shadcn/ui initialized; core primitives: MetricTile, Panel, StatusDot, DataTable shell
- Dashboard page structured to answer the five questions (fund performance, AI activity, intended trades, why, risk) with skeleton/empty states
- TanStack Query provider; Zustand store for UI state (sidebar, theme)
- WebSocket client hook consuming `/ws` with reconnect/backoff; live event ticker stub on dashboard
- Shared types imported from `packages/types`

### 2.4 Shared (packages/)

- `packages/types`: TypeScript API contract types (Health, Event, WS message envelope)
- `packages/ui`: shared primitives re-exported to apps/web
- `packages/config`: shared eslint/tsconfig/tailwind preset

### 2.5 Infrastructure

- `docker-compose.yml`: web, api, postgres (with pgvector extension), redis, worker
- Dockerfiles for web and api (multi-stage, non-root user)
- Makefile targets: `dev`, `build`, `test`, `lint`, `format`, `migrate`, `seed`, `down`
- `.env.example` with all required variables, no secrets committed
- CI (GitHub Actions): lint + typecheck + tests for api and web on PR

### 2.6 Security Baseline

- No secrets in code; env-only configuration
- Auth foundation: session/JWT scaffolding with a single admin user seed (full auth in later milestone)
- Security headers on web; input validation via Pydantic on api
- SECURITY.md documenting the baseline

---

## 3. M0 Definition of Done

- `docker compose up` brings up the full stack
- `GET /health` returns healthy status for api, db, redis
- Frontend loads at localhost with sidebar navigation across all workspace routes and the dark terminal theme
- Dashboard renders the five-question structure with skeleton states
- WebSocket connection established from web to api (visible heartbeat)
- Alembic migration applies cleanly; `events` table exists
- Celery worker processes the example task
- Model gateway interface compiles with provider stubs and telemetry schema
- All tests pass; lint and typecheck clean in CI
- All root docs present; CHANGELOG.md has an M0 entry; DECISIONS.md records stack choices

---

## 4. The Exact Cline Prompt for M0

Copy-paste the following as the first Cline task:

---

```text
You are building M0 (Foundation + Design System) of an AI-native quantitative
investment platform. This is a STRICTLY SCOPED task: build the foundation only.
Do NOT implement any trading agents, signals, investment committee, risk
engine, portfolio logic, or broker integration. Those come in later milestones
(docs/17_Milestone_Roadmap_M0_M10.md).

CONTEXT (read these first, in order):
- docs/14_TechStack_Evolved.md   (stack decisions — follow exactly)
- docs/15_Monorepo_Structure.md  (repo layout + frontend workspaces)
- docs/16_Design_System_Direction.md (visual direction + design tokens)
- docs/18_M0_Specification_Cline_Prompt.md §2 (detailed M0 requirements)

WORKING METHOD — follow this loop for the whole task:
1. Inspect the current workspace before writing anything.
2. Plan the file tree and confirm it matches docs/15 exactly.
3. Implement in this order: repo scaffolding → docker-compose → api → db
   migrations → model gateway interface → web shell → design system →
   websocket → tests → CI → docs.
4. After each major step, run the relevant build/test command and fix
   failures before continuing.
5. Never silently skip a requirement. If something is impossible, stop and
   report it.

HARD RULES:
- Monorepo layout exactly per docs/15_Monorepo_Structure.md. No top-level
  directories outside that structure.
- Backend: Python 3.12+, FastAPI, pydantic-settings, async SQLAlchemy,
  Alembic, Celery+Redis, pytest. Type hints everywhere. ruff + mypy clean.
- Frontend: Next.js App Router, TypeScript strict, Tailwind, shadcn/ui,
  TanStack Query, Zustand, TradingView Lightweight Charts installed
  (charts themselves come later). eslint clean.
- Shared TypeScript types live in packages/types only. No duplicated
  API contracts.
- PostgreSQL is the only database; enable pgvector. All schema changes via
  Alembic. Initial migration creates an append-only `events` table.
- Model gateway: interface + provider stubs + telemetry schema ONLY.
  No real LLM API calls in M0. No API keys in code — env vars only.
- Risk/agents/signals/portfolio/execution: DO NOT BUILD. Create empty
  service package skeletons with README stubs only.
- Frontend theme: dark institutional terminal per docs/16 — graphite
  background, near-black panels, restrained borders, tabular numerals,
  semantic status colors. NO neon crypto UI, NO generic SaaS cards,
  NO excessive gradients or rounded rectangles.
- All 12 workspace routes exist as placeholder pages with correct layout,
  sidebar navigation, and topbar (market status dot + clock).
- Dashboard page structurally answers the five questions from docs/16 §2
  using skeleton/empty states.
- WebSocket: api exposes /ws with a connection manager + heartbeat; web
  has a reconnecting client hook; dashboard shows a live event ticker stub.
- Celery: configured app + one `ping` example task; worker service in
  docker-compose.
- CI: GitHub Actions workflow running lint, typecheck, and tests for both
  api and web.
- Root docs: create AGENTS.md, ARCHITECTURE.md, DEVELOPMENT.md,
  DESIGN_SYSTEM.md, SECURITY.md, DECISIONS.md, CHANGELOG.md. AGENTS.md
  must contain the architecture rules, coding standards, database rules,
  testing requirements, UI rules, prohibited shortcuts, and definition of
  done from docs/15 §3.
- Every architectural choice you make gets a DECISIONS.md entry.
- Finish with a CHANGELOG.md entry for M0.

DEFINITION OF DONE (verify each before completing):
- `docker compose up` starts web, api, postgres (pgvector), redis, worker
- GET /health reports api + db + redis healthy
- Frontend loads with sidebar navigation across all 12 workspaces and the
  dark terminal theme
- Dashboard renders the five-question structure with skeletons
- WebSocket heartbeat visible between web and api
- Alembic migration applies cleanly; events table exists
- Celery worker executes the ping task
- Model gateway interface compiles with stubs + telemetry schema
- All tests pass; lint + typecheck clean
- All root docs present and accurate

When finished: run the full verification (compose up, health check,
tests, lint), report results, and STOP. Do not begin M1 or any agent
implementation.
```

---

## 5. After M0

Inspect what Cline produced before moving to M1:

1. `docker compose up` — does the stack come up?
2. Click through all 12 workspace routes — theme and navigation correct?
3. Health endpoint, WebSocket heartbeat, Celery ping verified?
4. Tests/lint/CI green?
5. Docs accurate?

Only then issue the M1 prompt (Market Intelligence), following the same strict pattern: context docs → working method → hard rules → definition of done → explicit stop boundary.