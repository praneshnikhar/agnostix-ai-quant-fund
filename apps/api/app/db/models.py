"""SQLAlchemy ORM models — M0 foundation.

Core entities follow `documents/04_Schemas.md` exactly:
users, proposals, critic_reviews, human_decisions, orders,
positions, portfolio_snapshots, agent_events.

Design rules:
- UUID primary keys
- timezone-aware timestamps (timestamptz)
- agent_events is append-only (enforced by convention + DB trigger-free
  application discipline; no UPDATE/DELETE paths exist in code)
- positions/portfolio_snapshots are synced snapshots — Alpaca remains the
  source of truth for brokerage account state.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base with consistent naming conventions."""


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """created_at / updated_at columns with DB-side defaults."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------


class UserRole(enum.StrEnum):
    PM = "pm"
    ADMIN = "admin"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), default=UserRole.VIEWER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# proposals
# ---------------------------------------------------------------------------


class ProposalStatus(enum.StrEnum):
    PENDING_CRITIC = "pending_critic"
    CRITIC_PASS = "critic_pass"
    CRITIC_PASS_WARNING = "critic_pass_warning"
    CRITIC_REJECT = "critic_reject"
    PENDING_HUMAN = "pending_human"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"
    EXECUTED = "executed"
    EXPIRED = "expired"


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # long|short
    thesis: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    entry_price: Mapped[float | None] = mapped_column(Numeric(18, 8))
    stop_loss: Mapped[float | None] = mapped_column(Numeric(18, 8))
    take_profit: Mapped[float | None] = mapped_column(Numeric(18, 8))
    size_pct_portfolio: Mapped[float | None] = mapped_column(Numeric(10, 6))
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(
        String(32), default=ProposalStatus.PENDING_CRITIC.value, index=True
    )

    __table_args__ = (
        Index("ix_proposals_symbol_created", "symbol", "created_at"),
    )


# ---------------------------------------------------------------------------
# critic_reviews
# ---------------------------------------------------------------------------


class CriticReview(Base):
    __tablename__ = "critic_reviews"

    id: Mapped[uuid.UUID] = _uuid_pk()
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True
    )
    # pass | pass_with_warning | reject
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_checks: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# human_decisions
# ---------------------------------------------------------------------------


class HumanDecision(Base):
    __tablename__ = "human_decisions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)  # approve|reject|revise
    revised_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = _uuid_pk()
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True
    )
    alpaca_order_id: Mapped[str | None] = mapped_column(Text, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    filled_price: Mapped[float | None] = mapped_column(Numeric(18, 8))
    filled_qty: Mapped[float | None] = mapped_column(Numeric(18, 8))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# positions (synced snapshot — Alpaca is source of truth)
# ---------------------------------------------------------------------------


class Position(Base):
    __tablename__ = "positions"

    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    qty: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    avg_entry_price: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    current_price: Mapped[float | None] = mapped_column(Numeric(18, 8))
    unrealized_pl: Mapped[float | None] = mapped_column(Numeric(18, 8))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# portfolio_snapshots
# ---------------------------------------------------------------------------


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = _uuid_pk()
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    equity: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    daily_pl: Mapped[float | None] = mapped_column(Numeric(18, 8))
    drawdown_pct: Mapped[float | None] = mapped_column(Numeric(10, 6))
    benchmark_return_pct: Mapped[float | None] = mapped_column(Numeric(10, 6))


# ---------------------------------------------------------------------------
# agent_events (append-only audit log)
# ---------------------------------------------------------------------------


class AgentEvent(Base):
    """Append-only audit event. Never updated or deleted by application code."""

    __tablename__ = "agent_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_agent_events_type_time", "event_type", "timestamp"),
        Index("ix_agent_events_agent_time", "agent_id", "timestamp"),
    )


# ---------------------------------------------------------------------------
# M1 — market intelligence
# ---------------------------------------------------------------------------


class Security(Base):
    """Reference metadata for tradable symbols."""

    __tablename__ = "securities"

    symbol: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    exchange: Mapped[str | None] = mapped_column(Text)
    asset_class: Mapped[str] = mapped_column(String(32), default="us_equity")
    status: Mapped[str] = mapped_column(String(16), default="active")
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_symbol_id: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MarketBar(Base):
    """OHLCV bar. Idempotent on (provider, symbol, timeframe, event_time)."""

    __tablename__ = "market_bars"

    id: Mapped[uuid.UUID] = _uuid_pk()
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 8), nullable=False)
    trade_count: Mapped[int | None]
    vwap: Mapped[float | None] = mapped_column(Numeric(18, 8))
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_market_bars_identity",
            "provider",
            "symbol",
            "timeframe",
            "event_time",
            unique=True,
        ),
        Index("ix_market_bars_symbol_tf_time", "symbol", "timeframe", "event_time"),
    )


class Quote(Base):
    """Quote tick. No uniqueness constraint by design: quotes are an
    append-only tick stream; deduplication would add write cost without
    analytical benefit. Freshness is judged by event_time, not row count."""

    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    bid_price: Mapped[float | None] = mapped_column(Numeric(18, 8))
    bid_size: Mapped[float | None] = mapped_column(Numeric(18, 8))
    ask_price: Mapped[float | None] = mapped_column(Numeric(18, 8))
    ask_size: Mapped[float | None] = mapped_column(Numeric(18, 8))
    last_price: Mapped[float | None] = mapped_column(Numeric(18, 8))
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_quotes_symbol_time", "symbol", "event_time"),)


class TradeRecord(Base):
    """Trade print. Deduplicated on the provider's trade id when present."""

    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = _uuid_pk()
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    size: Mapped[float] = mapped_column(Numeric(18, 8), nullable=False)
    conditions: Mapped[list | None] = mapped_column(JSONB)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_trade_id: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "uq_trades_provider_tid",
            "provider",
            "provider_trade_id",
            unique=True,
            postgresql_where=text("provider_trade_id IS NOT NULL"),
        ),
        Index("ix_trades_symbol_time", "symbol", "event_time"),
    )


class NewsArticleRecord(Base):
    """Normalized news article. First-write-wins on (provider, article id):
    original publication data is never overwritten by re-ingestion."""

    __tablename__ = "news_articles"

    id: Mapped[uuid.UUID] = _uuid_pk()
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_article_id: Mapped[str] = mapped_column(Text, nullable=False)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    symbols: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("uq_news_identity", "provider", "provider_article_id", unique=True),
        Index("ix_news_published_at", "published_at"),
        Index("ix_news_symbols_gin", "symbols", postgresql_using="gin"),
    )


class MarketSnapshotRecord(Base):
    """Persisted point-in-time snapshot payload (full JSONB incl.
    data_quality). Snapshots are immutable once written."""

    __tablename__ = "market_snapshots"

    id: Mapped[uuid.UUID] = _uuid_pk()
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    overall_state: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_status: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_market_snapshots_symbol_time", "symbol", "snapshot_time"),
    )


__all__ = [
    "AgentEvent",
    "Base",
    "CriticReview",
    "HumanDecision",
    "MarketBar",
    "MarketSnapshotRecord",
    "NewsArticleRecord",
    "Order",
    "PortfolioSnapshot",
    "Position",
    "Proposal",
    "ProposalStatus",
    "Quote",
    "Security",
    "TradeRecord",
    "User",
    "UserRole",
]
