
## [M2] Fundamental AI Intelligence

### Added
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
