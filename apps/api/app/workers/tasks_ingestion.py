"""M1 ingestion tasks.

Each task: fetch -> validate -> persist -> cache -> structured event.
Pure run_ingestion_* helpers are separated from Celery wrappers so they
are testable without a broker. Retries (exponential backoff) apply only
to transient provider errors; validation/persistence errors fail fast.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)

DEFAULT_WATCHLIST = "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD"


def load_watchlist() -> list[str]:
    raw = os.environ.get("MARKET_WATCHLIST", DEFAULT_WATCHLIST)
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


def _log_event(event_type: str, payload: dict[str, Any]) -> None:
    """Structured observability event. Never includes secrets."""
    logger.info("market_event type=%s %s", event_type, json.dumps(payload, default=str))


def _is_transient(exc: BaseException) -> bool:
    from market_data.providers.base import ProviderError

    if isinstance(exc, ProviderError):
        text = str(exc).lower()
        return any(k in text for k in ("timeout", "connection", "502", "503", "504", "429"))
    return False


# ---------------------------------------------------------------------------
# Pure ingestion helpers (broker-free, injectable fakes)
# ---------------------------------------------------------------------------


async def _persist_bars(rows: list[dict], repo_factory) -> int:
    async with repo_factory() as session:
        from app.db.repositories.market_data_repo import BarRepository

        return await BarRepository(session).upsert_bars(rows)


def run_ingestion_bars(
    symbol: str,
    timeframe: str = "1Day",
    provider=None,
    repo_factory=None,
    cache=None,
) -> dict[str, Any]:
    from datetime import UTC, datetime

    from market_data.cache import _key
    from market_data.validation import validate_bar

    received = datetime.now(UTC)
    fetched = provider.get_bars(symbol, timeframe=timeframe)
    _log_event(
        "market_data_received", {"symbol": symbol, "datatype": "bars", "count": len(fetched)}
    )
    valid, invalid = [], 0
    for bar in fetched:
        if validate_bar(bar):
            invalid += 1
            continue
        valid.append(
            {
                "symbol": bar.symbol,
                "timeframe": timeframe,
                "event_time": bar.event_time,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "trade_count": bar.trade_count,
                "vwap": bar.vwap,
                "provider": bar.provider_info.provider,
                "received_at": bar.received_at,
            }
        )
    persisted = asyncio.run(_persist_bars(valid, repo_factory)) if valid else 0
    _log_event(
        "market_data_persisted",
        {"symbol": symbol, "datatype": "bars", "persisted": persisted, "invalid": invalid},
    )
    if cache is not None and valid:
        latest = max(b.event_time for b in valid)
        summary = {"latest_event_time": latest.isoformat(), "received_at": received.isoformat()}
        asyncio.run(cache.set_json(_key("bars", symbol, timeframe), summary))
    return {"symbol": symbol, "datatype": "bars", "fetched": len(fetched),
            "valid": len(valid), "invalid": invalid, "persisted": persisted}


def run_ingestion_quotes(symbol: str, provider=None, repo_factory=None, cache=None) -> dict:
    from market_data.validation import validate_quote

    quote = provider.get_latest_quote(symbol)
    fetched = 1 if quote else 0
    persisted = 0
    if quote is not None and not validate_quote(quote):
        row = {
            "symbol": quote.symbol,
            "event_time": quote.event_time,
            "bid_price": quote.bid_price,
            "bid_size": quote.bid_size,
            "ask_price": quote.ask_price,
            "ask_size": quote.ask_size,
            "last_price": quote.last_price,
            "provider": quote.provider_info.provider,
            "received_at": quote.received_at,
        }

        async def _go():
            async with repo_factory() as session:
                from app.db.repositories.market_data_repo import QuoteRepository

                return await QuoteRepository(session).insert_quotes([row])

        persisted = asyncio.run(_go())
    return {"symbol": symbol, "datatype": "quotes", "fetched": fetched,
            "valid": fetched - (1 if quote and validate_quote(quote) else 0),
            "invalid": 1 if quote and validate_quote(quote) else 0, "persisted": persisted}


def run_ingestion_trades(symbol: str, limit: int = 50, provider=None, repo_factory=None) -> dict:
    from market_data.validation import validate_trade

    trades = provider.get_recent_trades(symbol, limit=limit)
    rows = []
    invalid = 0
    for t in trades:
        if validate_trade(t):
            invalid += 1
            continue
        rows.append({
            "symbol": t.symbol,
            "event_time": t.event_time,
            "price": t.price,
            "size": t.size,
            "conditions": t.conditions,
            "provider": t.provider_info.provider,
            "provider_trade_id": t.provider_trade_id,
            "received_at": t.received_at,
        })

    async def _go():
        async with repo_factory() as session:
            from app.db.repositories.market_data_repo import TradeRepository

            return await TradeRepository(session).insert_trades(rows)

    persisted = asyncio.run(_go()) if rows else 0
    return {"symbol": symbol, "datatype": "trades", "fetched": len(trades),
            "valid": len(rows), "invalid": invalid, "persisted": persisted}


def run_ingestion_news(limit: int = 50, symbols: list[str] | None = None,
                       provider=None, repo_factory=None) -> dict:
    from market_data.validation import validate_news

    articles = provider.get_news(symbols=symbols, limit=limit)
    rows = []
    invalid = 0
    for n in articles:
        if validate_news(n):
            invalid += 1
            continue
        rows.append({
            "provider": n.provider_info.provider,
            "provider_article_id": n.provider_article_id,
            "headline": n.headline,
            "summary": n.summary,
            "source": n.source,
            "url": n.url,
            "symbols": n.symbols,
            "published_at": n.published_at,
            "received_at": n.received_at,
        })

    async def _go():
        async with repo_factory() as session:
            from app.db.repositories.market_data_repo import NewsRepository

            return await NewsRepository(session).upsert_news(rows)

    persisted = asyncio.run(_go()) if rows else 0
    _log_event("news_persisted", {"persisted": persisted, "invalid": invalid})
    return {"symbol": None, "datatype": "news", "fetched": len(articles),
            "valid": len(rows), "invalid": invalid, "persisted": persisted}


def run_ingestion_security_metadata(symbol: str, provider=None, repo_factory=None) -> dict:
    security = provider.get_security(symbol)
    if security is None:
        return {"symbol": symbol, "datatype": "security_metadata",
                "fetched": 0, "valid": 0, "invalid": 0, "persisted": 0}
    row = {
        "symbol": security.symbol,
        "name": security.name,
        "exchange": security.exchange,
        "asset_class": security.asset_class,
        "status": security.status,
        "provider": security.provider_info.provider,
        "received_at": security.received_at,
    }

    async def _go():
        async with repo_factory() as session:
            from app.db.repositories.market_data_repo import SecurityRepository

            await SecurityRepository(session).upsert_security(row)

    asyncio.run(_go())
    return {"symbol": symbol, "datatype": "security_metadata",
            "fetched": 1, "valid": 1, "invalid": 0, "persisted": 1}


# ---------------------------------------------------------------------------
# Default wiring (real provider / real DB session factory)
# ---------------------------------------------------------------------------


def _repo_factory():
    """Async context manager yielding an AsyncSession."""
    from contextlib import asynccontextmanager

    from app.db.session import get_session_factory

    factory = get_session_factory()

    @asynccontextmanager
    async def _cm():
        async with factory() as session:
            yield session

    return _cm()


def _default_provider():
    from market_data.providers.alpaca_market_data import AlpacaMarketDataProvider

    return AlpacaMarketDataProvider()


def _default_news_provider():
    from market_data.providers.alpaca_news import AlpacaNewsProvider

    return AlpacaNewsProvider()


# ---------------------------------------------------------------------------
# Celery task wrappers
# ---------------------------------------------------------------------------


@shared_task(name="ingest_bars", bind=True, max_retries=3,
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def ingest_bars(self, symbol: str, timeframe: str = "1Day") -> dict:
    try:
        return run_ingestion_bars(symbol, timeframe=timeframe,
                                  provider=_default_provider(), repo_factory=_repo_factory)
    except Exception as exc:
        if _is_transient(exc):
            raise self.retry(exc=exc) from exc
        _log_event("data_ingestion_failed", {"symbol": symbol, "error": str(exc)})
        raise


@shared_task(name="ingest_quotes", bind=True, max_retries=3,
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def ingest_quotes(self, symbol: str) -> dict:
    try:
        return run_ingestion_quotes(symbol, provider=_default_provider(),
                                    repo_factory=_repo_factory)
    except Exception as exc:
        if _is_transient(exc):
            raise self.retry(exc=exc) from exc
        _log_event("data_ingestion_failed", {"symbol": symbol, "error": str(exc)})
        raise


@shared_task(name="ingest_trades", bind=True, max_retries=3,
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def ingest_trades(self, symbol: str, limit: int = 50) -> dict:
    try:
        return run_ingestion_trades(symbol, limit=limit,
                                    provider=_default_provider(), repo_factory=_repo_factory)
    except Exception as exc:
        if _is_transient(exc):
            raise self.retry(exc=exc) from exc
        _log_event("data_ingestion_failed", {"symbol": symbol, "error": str(exc)})
        raise


@shared_task(name="ingest_news", bind=True, max_retries=3,
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def ingest_news(self, limit: int = 50) -> dict:
    try:
        return run_ingestion_news(limit=limit, symbols=load_watchlist(),
                                  provider=_default_news_provider(), repo_factory=_repo_factory)
    except Exception as exc:
        if _is_transient(exc):
            raise self.retry(exc=exc) from exc
        _log_event("data_ingestion_failed", {"error": str(exc)})
        raise


@shared_task(name="ingest_security_metadata", bind=True, max_retries=3,
             retry_backoff=True, retry_backoff_max=600, retry_jitter=True)
def ingest_security_metadata(self, symbol: str) -> dict:
    try:
        return run_ingestion_security_metadata(symbol,
                                               provider=_default_provider(),
                                               repo_factory=_repo_factory)
    except Exception as exc:
        if _is_transient(exc):
            raise self.retry(exc=exc) from exc
        _log_event("data_ingestion_failed", {"symbol": symbol, "error": str(exc)})
        raise
