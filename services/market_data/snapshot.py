"""Market Snapshot service (M1).

Builds a point-in-time research view for one symbol from the internal
data-access layer (PostgreSQL via repositories). fundamentals/macro are
explicitly NOT populated in M1 — no fabrication. Data-quality states are
computed with configurable freshness thresholds.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from market_data.freshness import evaluate_freshness, load_thresholds_from_settings
from market_data.schemas import (
    FreshnessState,
    MarketDataStatus,
    MarketSnapshot,
    NewsArticle,
)


def _status(
    datatype: str, symbol: str, event_time: datetime | None, now: datetime
) -> MarketDataStatus:
    thresholds = load_thresholds_from_settings(None)
    threshold = thresholds.for_datatype(datatype)
    state, status = evaluate_freshness(event_time, now, threshold, symbol=symbol, datatype=datatype)
    if state is FreshnessState.MISSING:
        status.detail = "no data ingested"
    return status


def _news_schema(n) -> NewsArticle:
    return NewsArticle.model_validate(
        {
            "provider_article_id": n.provider_article_id,
            "headline": n.headline,
            "summary": n.summary,
            "source": n.source,
            "url": n.url,
            "symbols": n.symbols,
            "published_at": n.published_at,
            "received_at": n.received_at,
            "provider_info": {"provider": n.provider},
        }
    )


async def build_snapshot(session, symbol: str, *, now: datetime | None = None) -> MarketSnapshot:
    """Assemble the snapshot for `symbol` from stored (normalized) data.

    `now` lets callers pin the evaluation instant (e.g. the M2 research
    context pins its own `now`) so freshness states stay mutually
    consistent across the pipeline; defaults to wall clock.
    """
    from app.db.repositories.market_data_repo import (
        BarRepository,
        NewsRepository,
        QuoteRepository,
        SecurityRepository,
        TradeRepository,
    )

    symbol = symbol.upper()
    now = now or datetime.now(UTC)

    security = await SecurityRepository(session).get_by_symbol(symbol)
    latest_bar = await BarRepository(session).get_latest_bar(symbol)
    quote = await QuoteRepository(session).get_latest_quote(symbol)
    trades = await TradeRepository(session).get_recent_trades(symbol, limit=20)
    news = await NewsRepository(session).get_recent_news(symbols=[symbol], limit=10)

    market: dict = {}
    if latest_bar is not None:
        market["latest_bar"] = {
            "event_time": latest_bar.event_time,
            "open": latest_bar.open,
            "high": latest_bar.high,
            "low": latest_bar.low,
            "close": latest_bar.close,
            "volume": latest_bar.volume,
            "provider": latest_bar.provider,
            "received_at": latest_bar.received_at,
        }
    if quote is not None:
        market["quote"] = {
            "event_time": quote.event_time,
            "bid_price": quote.bid_price,
            "ask_price": quote.ask_price,
            "last_price": quote.last_price,
            "provider": quote.provider,
            "received_at": quote.received_at,
        }
    if trades:
        market["recent_trades"] = [
            {
                "event_time": t.event_time,
                "price": t.price,
                "size": t.size,
                "provider": t.provider,
                "received_at": t.received_at,
            }
            for t in trades
        ]
    if security is not None:
        market["security"] = {
            "name": security.name,
            "exchange": security.exchange,
            "asset_class": security.asset_class,
            "status": security.status,
        }

    data_quality = [
        _status("bars", symbol, latest_bar.event_time if latest_bar else None, now),
        _status("quotes", symbol, quote.event_time if quote else None, now),
        _status("trades", symbol, trades[0].event_time if trades else None, now),
        _status("news", symbol, news[0].published_at if news else None, now),
    ]

    return MarketSnapshot(
        symbol=symbol,
        generated_at=now,
        market=market,
        news=[_news_schema(n) for n in news],
        data_quality=data_quality,
    )


# ---------------------------------------------------------------------------
# M2 research-context projections (pure, deterministic; .clinerules §11/§12)
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    """Coerce runtime value types into JSON-stable primitives so the
    projection survives canonical serialization + content hashing."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def snapshot_research_summary(snapshot: MarketSnapshot) -> dict[str, Any]:
    """Deterministic, bounded projection of a snapshot for the M2 research
    context.

    Excludes wall-clock-volatile fields (`generated_at`, per-status
    `age_seconds`): the context layer carries build time separately and
    excludes it from the content hash, so identical underlying data yields
    an identical summary. Discrete freshness STATES are retained verbatim
    (fresh/stale/missing/invalid) — staleness is never hidden or upgraded.
    Trade prints collapse to a count to respect the context budget.
    """

    def _block(block: dict[str, Any]) -> dict[str, Any]:
        return {k: _jsonable(v) for k, v in block.items()}

    market: dict[str, Any] = {}
    for key, value in snapshot.market.items():
        if key == "recent_trades":
            market["recent_trades_count"] = len(value)
        else:
            market[key] = _block(value)

    data_quality = [
        {
            "datatype": s.datatype,
            "state": s.state.value,
            "as_of": s.as_of.isoformat() if s.as_of else None,
            "threshold_seconds": s.threshold_seconds,
            "detail": s.detail,
        }
        for s in snapshot.data_quality
    ]
    return {
        "symbol": snapshot.symbol,
        "overall_state": snapshot.overall_state.value,
        "data_quality": data_quality,
        "market": market,
    }


def context_news_items(articles: list[NewsArticle]) -> list[dict[str, Any]]:
    """Project normalized M1 news into M2 research-context dicts.

    Full provenance preserved (provider, provider article id, source, url,
    published/received timestamps, affected symbols). Pure — no LLM, no
    reordering: the context builder owns deterministic ordering/budget.
    """
    return [
        {
            "provider_article_id": a.provider_article_id,
            "headline": a.headline,
            "summary": a.summary,
            "source": a.source,
            "url": a.url,
            "symbols": list(a.symbols),
            "published_at": a.published_at,
            "received_at": a.received_at,
            "provider": a.provider_info.provider,
        }
        for a in articles
    ]
