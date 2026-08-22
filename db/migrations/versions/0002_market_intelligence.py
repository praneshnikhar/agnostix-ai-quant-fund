"""Market intelligence schema: securities, market_bars, quotes, trades,
news_articles, market_snapshots.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None

UUID = pg.UUID(as_uuid=True)
JSONB = pg.JSONB()
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    # --- securities ---
    op.create_table(
        "securities",
        sa.Column("symbol", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("asset_class", sa.String(32), nullable=False, server_default="us_equity"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_symbol_id", sa.Text(), nullable=True),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )

    # --- market_bars ---
    op.create_table(
        "market_bars",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.String(16), nullable=False),
        sa.Column("event_time", TIMESTAMPTZ, nullable=False),
        sa.Column("open", sa.Numeric(18, 8), nullable=False),
        sa.Column("high", sa.Numeric(18, 8), nullable=False),
        sa.Column("low", sa.Numeric(18, 8), nullable=False),
        sa.Column("close", sa.Numeric(18, 8), nullable=False),
        sa.Column("volume", sa.Numeric(24, 8), nullable=False),
        sa.Column("trade_count", sa.Integer(), nullable=True),
        sa.Column("vwap", sa.Numeric(18, 8), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_market_bars_identity",
        "market_bars",
        ["provider", "symbol", "timeframe", "event_time"],
    )
    op.create_index(
        "ix_market_bars_symbol_tf_time", "market_bars", ["symbol", "timeframe", "event_time"]
    )

    # --- quotes ---
    op.create_table(
        "quotes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("event_time", TIMESTAMPTZ, nullable=False),
        sa.Column("bid_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("bid_size", sa.Numeric(18, 8), nullable=True),
        sa.Column("ask_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("ask_size", sa.Numeric(18, 8), nullable=True),
        sa.Column("last_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_quotes_symbol_time", "quotes", ["symbol", "event_time"])

    # --- trades ---
    op.create_table(
        "trades",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("event_time", TIMESTAMPTZ, nullable=False),
        sa.Column("price", sa.Numeric(18, 8), nullable=False),
        sa.Column("size", sa.Numeric(18, 8), nullable=False),
        sa.Column("conditions", JSONB, nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_trade_id", sa.Text(), nullable=True),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_trades_provider_tid",
        "trades",
        ["provider", "provider_trade_id"],
        unique=True,
        postgresql_where=sa.text("provider_trade_id IS NOT NULL"),
    )
    op.create_index("ix_trades_symbol_time", "trades", ["symbol", "event_time"])

    # --- news_articles ---
    op.create_table(
        "news_articles",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_article_id", sa.Text(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("symbols", JSONB, nullable=False),
        sa.Column("published_at", TIMESTAMPTZ, nullable=False),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_news_identity", "news_articles", ["provider", "provider_article_id"]
    )
    op.create_index("ix_news_published_at", "news_articles", ["published_at"])
    op.create_index(
        "ix_news_symbols_gin", "news_articles", ["symbols"], postgresql_using="gin"
    )

    # --- market_snapshots ---
    op.create_table(
        "market_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("snapshot_time", TIMESTAMPTZ, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("overall_state", sa.String(16), nullable=False),
        sa.Column("provider_status", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_market_snapshots_symbol_time", "market_snapshots", ["symbol", "snapshot_time"]
    )


def downgrade() -> None:
    op.drop_table("market_snapshots")
    op.drop_table("news_articles")
    op.drop_table("trades")
    op.drop_table("quotes")
    op.drop_table("market_bars")
    op.drop_table("securities")
