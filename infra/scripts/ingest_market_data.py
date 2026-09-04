"""One-shot market-data ingestion CLI (M1).

Fetches and persists securities, bars, quotes, trades, and news for the
development watchlist from Alpaca (paper / IEX). Intended for local demo —
populate the stores so the markets UI has charts/news to render.

Run (requires a migrated PostgreSQL database and Alpaca paper keys):

    python -m infra.scripts.ingest_market_data
    python -m infra.scripts.ingest_market_data --symbols AAPL,MSFT
    python -m infra.scripts.ingest_market_data --skip-news

Credentials are read from settings (API_ALPACA_API_KEY / API_ALPACA_SECRET_KEY),
never from this file. Each datatype is isolated: one failure does not abort the
rest of the run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
sys.path.insert(0, str(REPO_ROOT / "services"))

DEFAULT_WATCHLIST = "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD"


def _providers():
    from app.core.config import get_settings
    from market_data.providers.alpaca_market_data import AlpacaMarketDataProvider
    from market_data.providers.alpaca_news import AlpacaNewsProvider

    s = get_settings()
    if not s.alpaca_api_key or not s.alpaca_secret_key:
        raise SystemExit("API_ALPACA_API_KEY / API_ALPACA_SECRET_KEY not set in .env")
    market = AlpacaMarketDataProvider(api_key=s.alpaca_api_key, secret_key=s.alpaca_secret_key)
    news = AlpacaNewsProvider(api_key=s.alpaca_api_key, secret_key=s.alpaca_secret_key)
    return market, news


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ingest_market_data",
        description="Ingest market data for the development watchlist.",
    )
    parser.add_argument(
        "--symbols",
        default=os.environ.get("MARKET_WATCHLIST", DEFAULT_WATCHLIST),
        help="Comma-separated tickers (default: MARKET_WATCHLIST env or built-in list)",
    )
    parser.add_argument("--skip-news", action="store_true", help="Skip news ingestion")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if not symbols:
        raise SystemExit("no symbols provided")

    from app.workers.tasks_ingestion import (
        run_ingestion_bars,
        run_ingestion_news,
        run_ingestion_quotes,
        run_ingestion_security_metadata,
        run_ingestion_trades,
    )

    market_provider, news_provider = _providers()

    # Each run_ingestion_* helper runs its own asyncio.run() (a fresh event
    # loop). The process-wide engine's connection pool would otherwise hand a
    # connection bound to a closed loop back to the next call, so use a
    # per-call NullPool engine here instead.
    from contextlib import asynccontextmanager

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import get_settings

    def repo():
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

        @asynccontextmanager
        async def _cm():
            async with factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise
            await engine.dispose()

        return _cm()

    summary: dict = {"symbols": []}
    for sym in symbols:
        results: dict = {}
        for datatype, fn in (
            ("security", run_ingestion_security_metadata),
            ("bars", run_ingestion_bars),
            ("quotes", run_ingestion_quotes),
            ("trades", run_ingestion_trades),
        ):
            try:
                results[datatype] = fn(sym, provider=market_provider, repo_factory=repo)
            except Exception as exc:  # noqa: BLE001 — isolate per-datatype failures
                results[datatype] = {"error": str(exc)[:200]}
        summary["symbols"].append({"symbol": sym, **results})

    if not args.skip_news:
        try:
            summary["news"] = run_ingestion_news(
                symbols=symbols, provider=news_provider, repo_factory=repo
            )
        except Exception as exc:  # noqa: BLE001
            summary["news"] = {"error": str(exc)[:200]}

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
