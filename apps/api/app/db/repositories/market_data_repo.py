"""Market-data repositories (M1).

Async data-access boundary over the M1 tables. All writes are idempotent:

- securities      : ON CONFLICT (symbol) DO UPDATE — latest provider record wins.
- market_bars     : ON CONFLICT (provider, symbol, timeframe, event_time)
                    DO UPDATE — re-ingestion refreshes OHLCV in place.
- quotes          : append-only tick stream, no dedupe (see model docstring).
- trades          : ON CONFLICT DO NOTHING on partial unique
                    (provider, provider_trade_id) WHERE NOT NULL.
- news_articles   : ON CONFLICT (provider, provider_article_id) DO NOTHING —
                    first-write-wins; original publication data is preserved.
- market_snapshots: immutable inserts.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    MarketBar,
    MarketSnapshotRecord,
    NewsArticleRecord,
    Quote,
    Security,
    TradeRecord,
)


class SecurityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_security(self, values: dict) -> None:
        stmt = pg_insert(Security).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol"],
            set_={
                "name": stmt.excluded.name,
                "exchange": stmt.excluded.exchange,
                "asset_class": stmt.excluded.asset_class,
                "status": stmt.excluded.status,
                "provider": stmt.excluded.provider,
                "provider_symbol_id": stmt.excluded.provider_symbol_id,
                "received_at": stmt.excluded.received_at,
            },
        )
        await self._session.execute(stmt)

    async def get_all(self) -> list[Security]:
        result = await self._session.execute(select(Security).order_by(Security.symbol))
        return list(result.scalars())

    async def get_by_symbol(self, symbol: str) -> Security | None:
        result = await self._session.execute(
            select(Security).where(Security.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()


class BarRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_bars(self, rows: list[dict]) -> int:
        """Bulk idempotent bar write. Returns affected row count."""
        if not rows:
            return 0
        stmt = pg_insert(MarketBar).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["provider", "symbol", "timeframe", "event_time"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "trade_count": stmt.excluded.trade_count,
                "vwap": stmt.excluded.vwap,
                "received_at": stmt.excluded.received_at,
            },
        )
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_bars(
        self,
        symbol: str,
        timeframe: str = "1Day",
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[MarketBar]:
        q = (
            select(MarketBar)
            .where(MarketBar.symbol == symbol.upper(), MarketBar.timeframe == timeframe)
            .order_by(MarketBar.event_time.desc())
            .limit(limit)
        )
        if start is not None:
            q = q.where(MarketBar.event_time >= start)
        if end is not None:
            q = q.where(MarketBar.event_time <= end)
        result = await self._session.execute(q)
        return list(result.scalars())

    async def get_latest_bar(self, symbol: str, timeframe: str = "1Day") -> MarketBar | None:
        result = await self._session.execute(
            select(MarketBar)
            .where(MarketBar.symbol == symbol.upper(), MarketBar.timeframe == timeframe)
            .order_by(MarketBar.event_time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class QuoteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_quotes(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        result = await self._session.execute(pg_insert(Quote).values(rows))
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_latest_quote(self, symbol: str) -> Quote | None:
        result = await self._session.execute(
            select(Quote)
            .where(Quote.symbol == symbol.upper())
            .order_by(Quote.event_time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class TradeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_trades(self, rows: list[dict]) -> int:
        """Idempotent on (provider, provider_trade_id) when trade id present."""
        if not rows:
            return 0
        stmt = pg_insert(TradeRecord).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["provider", "provider_trade_id"]
        )
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_recent_trades(self, symbol: str, limit: int = 50) -> list[TradeRecord]:
        result = await self._session.execute(
            select(TradeRecord)
            .where(TradeRecord.symbol == symbol.upper())
            .order_by(TradeRecord.event_time.desc())
            .limit(limit)
        )
        return list(result.scalars())


class NewsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_news(self, rows: list[dict]) -> int:
        """First-write-wins on (provider, provider_article_id)."""
        if not rows:
            return 0
        stmt = pg_insert(NewsArticleRecord).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["provider", "provider_article_id"]
        )
        result = await self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    async def get_recent_news(
        self,
        symbols: list[str] | None = None,
        limit: int = 50,
        since: datetime | None = None,
    ) -> list[NewsArticleRecord]:
        q = select(NewsArticleRecord).order_by(NewsArticleRecord.published_at.desc()).limit(limit)
        if symbols:
            q = q.where(NewsArticleRecord.symbols.contains([s.upper() for s in symbols]))
        if since is not None:
            q = q.where(NewsArticleRecord.published_at >= since)
        result = await self._session.execute(q)
        return list(result.scalars())


class SnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_snapshot(self, values: dict) -> MarketSnapshotRecord:
        record = MarketSnapshotRecord(**values)
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_latest_snapshot(self, symbol: str) -> MarketSnapshotRecord | None:
        result = await self._session.execute(
            select(MarketSnapshotRecord)
            .where(MarketSnapshotRecord.symbol == symbol.upper())
            .order_by(MarketSnapshotRecord.snapshot_time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
