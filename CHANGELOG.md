
## [M1] Market Intelligence Foundation

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
