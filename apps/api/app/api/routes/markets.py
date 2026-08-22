"""M1 read-only market intelligence API.

All responses use internal schemas — no provider-specific objects.
No trading endpoints exist in M1. Read-only by design.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.market_data_repo import (
    BarRepository,
    NewsRepository,
    QuoteRepository,
    SecurityRepository,
    SnapshotRepository,
    TradeRepository,
)
from app.db.session import get_session
from market_data.snapshot import build_snapshot

router = APIRouter(prefix="/markets", tags=["markets"])


class WatchlistEntry(BaseModel):
    symbol: str
    name: str | None = None
    exchange: str | None = None


class MarketsResponse(BaseModel):
    watchlist: list[WatchlistEntry]
    generated_at: datetime


def _bar_out(b) -> dict:
    return {
        "symbol": b.symbol, "timeframe": b.timeframe, "event_time": b.event_time,
        "open": b.open, "high": b.high, "low": b.low, "close": b.close,
        "volume": b.volume, "trade_count": b.trade_count, "vwap": b.vwap,
        "provider": b.provider, "received_at": b.received_at,
    }


def _news_out(n) -> dict:
    return {
        "id": str(n.id), "headline": n.headline, "summary": n.summary,
        "source": n.source, "url": n.url, "symbols": n.symbols,
        "published_at": n.published_at, "received_at": n.received_at,
        "provider": n.provider,
    }


@router.get("", response_model=MarketsResponse)
async def list_markets(session: AsyncSession = Depends(get_session)) -> MarketsResponse:
    """Development watchlist + security metadata (configurable universe)."""
    import os

    symbols = [
        s.strip().upper()
        for s in os.environ.get(
            "MARKET_WATCHLIST", "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA,AMD"
        ).split(",")
        if s.strip()
    ]
    entries: list[WatchlistEntry] = []
    repo = SecurityRepository(session)
    for sym in symbols:
        sec = await repo.get_by_symbol(sym)
        entries.append(
            WatchlistEntry(symbol=sym, name=sec.name if sec else None,
                           exchange=sec.exchange if sec else None)
        )
    return MarketsResponse(watchlist=entries, generated_at=datetime.now(UTC))


@router.get("/{symbol}")
async def get_market(symbol: str, session: AsyncSession = Depends(get_session)) -> dict:
    sec = await SecurityRepository(session).get_by_symbol(symbol)
    if sec is None:
        raise HTTPException(status_code=404, detail=f"unknown symbol {symbol.upper()}")
    return {
        "symbol": sec.symbol, "name": sec.name, "exchange": sec.exchange,
        "asset_class": sec.asset_class, "status": sec.status,
        "provider": sec.provider, "received_at": sec.received_at,
    }


@router.get("/{symbol}/bars")
async def get_bars(
    symbol: str,
    timeframe: str = Query(default="1Day", pattern="^(1Min|1Hour|1Day)$"),
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    session: AsyncSession = Depends(get_session),
) -> dict:
    bars = await BarRepository(session).get_bars(symbol, timeframe, start, end, limit)
    return {"symbol": symbol.upper(), "timeframe": timeframe,
            "count": len(bars), "bars": [_bar_out(b) for b in bars]}


@router.get("/{symbol}/quotes")
async def get_quotes(symbol: str, session: AsyncSession = Depends(get_session)) -> dict:
    q = await QuoteRepository(session).get_latest_quote(symbol)
    if q is None:
        return {"symbol": symbol.upper(), "quote": None}
    return {
        "symbol": q.symbol, "quote": {
            "event_time": q.event_time, "bid_price": q.bid_price,
            "bid_size": q.bid_size, "ask_price": q.ask_price,
            "ask_size": q.ask_size, "last_price": q.last_price,
            "provider": q.provider, "received_at": q.received_at,
        }
    }


@router.get("/{symbol}/trades")
async def get_trades(
    symbol: str, limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> dict:
    trades = await TradeRepository(session).get_recent_trades(symbol, limit)
    return {
        "symbol": symbol.upper(), "count": len(trades),
        "trades": [{
            "event_time": t.event_time, "price": t.price, "size": t.size,
            "conditions": t.conditions, "provider": t.provider,
            "provider_trade_id": t.provider_trade_id, "received_at": t.received_at,
        } for t in trades],
    }


@router.get("/{symbol}/news")
async def get_news(
    symbol: str, limit: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> dict:
    articles = await NewsRepository(session).get_recent_news(symbols=[symbol], limit=limit)
    return {"symbol": symbol.upper(), "count": len(articles),
            "articles": [_news_out(n) for n in articles]}


@router.get("/{symbol}/snapshot")
async def get_snapshot(
    symbol: str, persist: bool = False, session: AsyncSession = Depends(get_session)
) -> dict:
    snapshot = await build_snapshot(session, symbol)
    if persist:
        await SnapshotRepository(session).save_snapshot({
            "symbol": snapshot.symbol,
            "snapshot_time": snapshot.generated_at,
            "payload": snapshot.model_dump(mode="json"),
            "overall_state": snapshot.overall_state.value,
        })
        await session.commit()
    return snapshot.model_dump(mode="json")
