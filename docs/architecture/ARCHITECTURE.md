
## M1 — Market Intelligence (IMPLEMENTED)

- Data domain (`services/market_data`): typed schemas (Bar, Quote, Trade,
  NewsArticle, Security, MarketDataStatus, MarketSnapshot), deterministic
  normalization/validation, configurable freshness thresholds
  (FRESH/STALE/MISSING/INVALID), provenance on every record
  (provider / event_time / received_at / stored_at).
- Providers: `AlpacaMarketDataProvider` and `AlpacaNewsProvider` behind the
  `MarketDataProvider` interface; alpaca-py imported lazily; paper/IEX feed.
- Storage: PostgreSQL tables for bars/quotes/trades/news/securities/snapshots
  (migration 0002) with idempotency upserts; Redis short-lived cache with TTLs.
- Workers: Celery ingestion tasks (bars, quotes, trades, news, security
  metadata) with exponential-backoff retries for transient errors only;
  structured lifecycle events; no LLM usage anywhere in ingestion.
- Snapshot service: point-in-time per-symbol view incl. data-quality states;
  fundamentals/macro explicitly `unavailable_in_m1`.
- API: read-only `/markets*` endpoints using internal schemas only.
- Frontend: `/markets` watchlist + search; `/markets/[symbol]` price, chart
  (lightweight-charts), market data, news, freshness badges.
- Agent permissions: READ_MARKET_DATA / READ_NEWS / READ_SNAPSHOT granted to
  research role; PLACE_ORDER remains execution-only and unused in M1.

## M1 — Planned / Not Implemented

- Realtime Alpaca streaming (polling-based ingestion only; event interface
  reserved: market_update, quote_update, trade_update, news_update).
- Fundamentals & macro data (M2+). Sentiment/LLM analysis (M2+). Any trading.
