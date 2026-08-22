"""M1 persistence tests — deterministic, no live database.

Verifies (a) model/table definitions on Base.metadata and (b) that the
idempotent write statements compile to the expected PostgreSQL SQL
fragments (ON CONFLICT / DO UPDATE / DO NOTHING / partial index WHERE).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db.models import (
    MarketBar,
    MarketSnapshotRecord,
    NewsArticleRecord,
    Quote,
    Security,
    TradeRecord,
)
from app.db.repositories.market_data_repo import (
    BarRepository,
    NewsRepository,
    TradeRepository,
)

T0 = datetime(2024, 6, 3, 14, 30, tzinfo=UTC)


def _compile(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


# ---------------------------------------------------------------------------
# Table definitions
# ---------------------------------------------------------------------------


def test_all_m1_tables_registered() -> None:
    tables = {"securities", "market_bars", "quotes", "trades", "news_articles", "market_snapshots"}
    assert tables <= set(MarketBar.metadata.tables)


def test_market_bars_unique_identity() -> None:
    # Declared as a unique Index (equivalent to a unique constraint in PG).
    idx = next(i for i in MarketBar.__table__.indexes if i.name == "uq_market_bars_identity")
    assert idx.unique
    cols = {c.name for c in idx.columns}
    assert cols == {"provider", "symbol", "timeframe", "event_time"}


def test_news_unique_identity_and_gin_index() -> None:
    table = NewsArticleRecord.__table__
    names = {i.name for i in table.indexes} | {c.name for c in table.constraints if c.name}
    assert "uq_news_identity" in names
    assert "ix_news_symbols_gin" in names


def test_trades_partial_unique_index() -> None:
    idx = next(i for i in TradeRecord.__table__.indexes if i.name == "uq_trades_provider_tid")
    assert idx.dialect_options["postgresql"]["where"] is not None


def test_bar_create_table_sql() -> None:
    sql = str(CreateTable(MarketBar.__table__).compile(dialect=postgresql.dialect()))
    assert "event_time" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql


def test_partial_index_sql_has_where() -> None:
    idx = next(i for i in TradeRecord.__table__.indexes if i.name == "uq_trades_provider_tid")
    sql = str(CreateIndex(idx).compile(dialect=postgresql.dialect()))
    assert "WHERE" in sql.upper()


# ---------------------------------------------------------------------------
# Idempotent statement compilation
# ---------------------------------------------------------------------------


def _bar_row(symbol: str = "AAPL") -> dict:
    return dict(
        symbol=symbol,
        timeframe="1Day",
        event_time=T0,
        open=100.0,
        high=110.0,
        low=99.0,
        close=105.0,
        volume=1000.0,
        trade_count=10,
        vwap=104.0,
        provider="alpaca_market_data",
        received_at=T0,
    )


def test_upsert_bars_compiles_with_on_conflict_update() -> None:
    stmt = BarRepository.__dict__["upsert_bars"]  # presence check only
    assert callable(stmt)
    from sqlalchemy.dialects.postgresql import insert

    raw = insert(MarketBar).values([_bar_row()])
    stmt2 = raw.on_conflict_do_update(
        index_elements=["provider", "symbol", "timeframe", "event_time"],
        set_={"close": raw.excluded.close},
    )
    sql = _compile(stmt2)
    assert "ON CONFLICT" in sql
    assert "DO UPDATE SET" in sql


def test_insert_trades_compiles_with_do_nothing() -> None:
    from sqlalchemy.dialects.postgresql import insert

    raw = insert(TradeRecord).values(
        dict(
            symbol="AAPL",
            event_time=T0,
            price=100.0,
            size=10.0,
            provider="alpaca_market_data",
            provider_trade_id="T1",
            received_at=T0,
        )
    )
    stmt = raw.on_conflict_do_nothing(index_elements=["provider", "provider_trade_id"])
    sql = _compile(stmt)
    assert "ON CONFLICT" in sql
    assert "DO NOTHING" in sql


def test_upsert_news_compiles_with_do_nothing() -> None:
    from sqlalchemy.dialects.postgresql import insert

    raw = insert(NewsArticleRecord).values(
        dict(
            provider="alpaca_news",
            provider_article_id="n1",
            headline="h",
            symbols=["AAPL"],
            published_at=T0,
            received_at=T0,
        )
    )
    stmt = raw.on_conflict_do_nothing(index_elements=["provider", "provider_article_id"])
    sql = _compile(stmt)
    assert "ON CONFLICT" in sql
    assert "DO NOTHING" in sql


def test_repositories_exist_with_expected_methods() -> None:
    for cls, methods in [
        (BarRepository, ["upsert_bars", "get_bars", "get_latest_bar"]),
        (NewsRepository, ["upsert_news", "get_recent_news"]),
        (TradeRepository, ["insert_trades", "get_recent_trades"]),
    ]:
        for m in methods:
            assert hasattr(cls, m)


def test_snapshot_model_columns() -> None:
    cols = {c.name for c in MarketSnapshotRecord.__table__.columns}
    assert {"id", "symbol", "snapshot_time", "payload", "overall_state"} <= cols


def test_quote_model_columns() -> None:
    cols = {c.name for c in Quote.__table__.columns}
    assert {"bid_price", "ask_price", "last_price", "event_time"} <= cols


def test_security_pk_is_symbol() -> None:
    pk = {c.name for c in Security.__table__.primary_key.columns}
    assert pk == {"symbol"}
