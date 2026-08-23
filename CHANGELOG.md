
## [M2] Fundamental AI Intelligence

### Added
- Provider-agnostic model platform (M2.3): a SINGLE provider registry in
  the existing ModelGateway — get_model_gateway(provider, model) returns
  the same normalized internal contract for every category. First-class
  providers: openrouter (cloud aggregator; bounded retries on 429/5xx/
  network only, explicit timeouts, JSON-mode structured output with schema
  hint), ollama (local/offline; fully configurable host + explicit model
  id — no hardcoded localhost/model/GPU), and custom (generic self-hosted /
  OpenAI-compatible endpoints: vLLM/TGI/private/fine-tuned Agnostix models;
  configurable base URL, optional bearer auth, extra headers). ModelResponse
  now carries requested_model vs provider-served model id, finish_reason,
  and benign provider_metadata; missing token/cost metadata stays None.
  Domain layer (agent/critic/context/grounding/evaluation/services) has
  ZERO provider imports — enforced by test. Evaluation CLI resolves any
  registered provider via the registry (no provider-specific logic).
- services/fundamentals: typed domain schemas (CompanyProfile,
  FinancialMetric, FinancialPeriod, statements, EarningsEvent/Result,
  ValuationSnapshot, FundamentalDataStatus, ResearchDocument)
- Provider abstractions (FundamentalsProvider, CompanyDataProvider,
  EarningsProvider, ValuationProvider, DocumentsProvider) with a fully
  deterministic fixture implementation; no third-party fundamentals API
  is required or fabricated
- Deterministic derived metrics (revenue growth, margins, net debt, FCF,
  earnings surprises) with formula + inputs + timestamp provenance
- Data validation/quality flagging: conflicts preserved, never corrected;
  period/currency/unit/timestamp integrity rules
- FundamentalResearchContext builder: bounded, deterministic, versioned +
  content-hashed context with explicit data-gap reporting
- FundamentalResearchAgent (structured InvestmentThesis output: view,
  confidence, facts/interpretation/conclusion separation, evidence refs,
  catalysts, risks, bear case, invalidation conditions) via Model Gateway
- FundamentalResearchCritic: deterministic grounding checks are
  authoritative (evidence existence, numerical traceability, calibration);
  optional LLM review can only escalate, never downgrade
- Model evaluation harness (per-run records: provider/model/prompt
  version/latency/success/schema validity/critic verdict) + report summary
- Research context integrates M1 market intelligence: normalized news
  (full provenance: provider, article id, source, url, published/received
  timestamps, symbols) with deterministic newest-first ordering, stable
  tie-breaks, dedupe, and a bounded budget; plus a bounded MarketSnapshot
  projection carrying discrete freshness states (fresh/stale/missing/
  invalid) per datatype. Missing or stale inputs are reported as explicit
  data gaps — never fabricated or silently omitted. Context version
  bumped m2-v1 → m2-v2 because the hashed payload shape changed materially.
- Operational multi-model evaluation runner (M2.2): ONE immutable research
  context is built exactly once per run; every configured provider/model
  target is evaluated against that identical context (same context version
  + hash, prompt version, facts, news, snapshot, documents), followed by
  deterministic grounding + critic per model. Identical-context invariant
  fails the whole run rather than comparing different contexts; per-model
  failures are isolated (status=failed + structured error, no fabricated
  output); ordering follows configuration order deterministically. Metrics:
  provider/model/served model_version, prompt+agent versions, latency,
  input/output/total tokens, estimated cost (None when a provider does not
  report it — never fabricated), schema validity, critic verdict,
  grounding result, evidence coverage, data-quality gaps.
- evaluation_runs table (migration 0004) + repository: one row per
  multi-model evaluation over a single context, storing reproduction
  metadata (context version/hash, prompt/agent versions, ordered model
  config) and the full ordered report as JSONB; correlated audit events
  (evaluation_requested/context_created/model_finished/completed|failed)
- CLI entry point: python -m infra.scripts.evaluate_models --symbol ACME
  --model PROVIDER:MODEL [--model ...] [--dry-run]; providers resolve via
  existing Model Gateway adapters (extensible; unknown/unconfigured
  providers fail only their own record)
- Research event persistence (research_requested → research_completed)
- PostgreSQL migration 0003 (fundamental intelligence schema incl.
  research_runs and human-feedback foundation table)
- /research API endpoints (read-only GETs + POST run; no order capability)
- Web research workspace (/research, /research/[symbol]) with thesis,
  financials, earnings, evidence, critic verdict, model metadata,
  history comparison, loading/empty/error/insufficient-data states

### Security
- Research agents hold read/write-research permissions only; PLACE_ORDER
  and MODIFY_PORTFOLIO remain ungranted. No execution path exists in M2.

### Fixed
- Alembic now normalizes the async (+asyncpg) DB URL to psycopg2 for
  synchronous migration execution.

[M1] Market Intelligence Foundation

### Added
- services/market_data: schemas, normalization, validation, freshness,
  provenance, cache, snapshot service, Alpaca providers (market data + news)
- PostgreSQL migration 0002 (bars/quotes/trades/news/securities/snapshots)
- Celery ingestion workers with retry/backoff and structured events
- Read-only /markets API endpoints
- Web market explorer (/markets, /markets/[symbol]) with charts and
  data-quality badges
- Agent READ_SNAPSHOT permission (research role)

### Security
- Paper/IEX only; no order placement capability added.

## M2.5 — Provider Management Backend

- Added authenticated AI/data provider configuration CRUD with explicit scopes.
- Added Fernet-encrypted provider credentials, masked safe responses, and
  secret-free audit events.
- Added safe connection testing, model discovery, default model persistence,
  and canonical provider/model records through the existing ModelGateway seam.
- Added Alpaca stored-credential injection into the existing M1 market-data and
  news adapters without adding trading capability.
