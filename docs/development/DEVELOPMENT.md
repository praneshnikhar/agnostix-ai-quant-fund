
## M1 Development Notes

- Watchlist configured via `MARKET_WATCHLIST` env var
  (default AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD).
- Freshness thresholds configurable via env-derived settings dict
  (`load_thresholds_from_settings`); documented defaults: bars 24h,
  quotes 60s, trades 5min, news 6h, security metadata 7d.
- Run ingestion manually: celery worker tasks `ingest_bars`, `ingest_news`,
  etc. (see apps/api/app/workers/tasks_ingestion.py).
- Tests: `python -m pytest apps/api/tests services/market_data/tests`;
  frontend: `cd apps/web && npm test`. CI never calls live Alpaca APIs.
