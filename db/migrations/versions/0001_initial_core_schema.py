"""Initial core schema: users, proposals, critic_reviews, human_decisions,
orders, positions, portfolio_snapshots, agent_events.

Follows documents/04_Schemas.md exactly.

Revision ID: 0001
Revises:
Create Date: 2026-08-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

UUID = pg.UUID(as_uuid=True)
JSONB = pg.JSONB()
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    # --- proposals ---
    op.create_table(
        "proposals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("thesis", sa.Text(), nullable=False),
        sa.Column("evidence", JSONB, nullable=True),
        sa.Column("entry_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("stop_loss", sa.Numeric(18, 8), nullable=True),
        sa.Column("take_profit", sa.Numeric(18, 8), nullable=True),
        sa.Column("size_pct_portfolio", sa.Numeric(10, 6), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_critic"),
    )
    op.create_index("ix_proposals_status", "proposals", ["status"])
    op.create_index("ix_proposals_symbol_created", "proposals", ["symbol", "created_at"])

    # --- critic_reviews ---
    op.create_table(
        "critic_reviews",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "proposal_id", UUID, sa.ForeignKey("proposals.id"), nullable=False, index=True
        ),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("rule_checks", JSONB, nullable=True),
        sa.Column("llm_notes", sa.Text(), nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )

    # --- human_decisions ---
    op.create_table(
        "human_decisions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "proposal_id", UUID, sa.ForeignKey("proposals.id"), nullable=False, index=True
        ),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("revised_fields", JSONB, nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )

    # --- orders ---
    op.create_table(
        "orders",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "proposal_id", UUID, sa.ForeignKey("proposals.id"), nullable=False, index=True
        ),
        sa.Column("alpaca_order_id", sa.Text(), nullable=True, index=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("filled_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("filled_qty", sa.Numeric(18, 8), nullable=True),
        sa.Column("submitted_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )

    # --- positions (synced snapshot; Alpaca is source of truth) ---
    op.create_table(
        "positions",
        sa.Column("symbol", sa.Text(), primary_key=True),
        sa.Column("qty", sa.Numeric(18, 8), nullable=False),
        sa.Column("avg_entry_price", sa.Numeric(18, 8), nullable=False),
        sa.Column("current_price", sa.Numeric(18, 8), nullable=True),
        sa.Column("unrealized_pl", sa.Numeric(18, 8), nullable=True),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )

    # --- portfolio_snapshots ---
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("timestamp", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("equity", sa.Numeric(18, 8), nullable=False),
        sa.Column("cash", sa.Numeric(18, 8), nullable=False),
        sa.Column("daily_pl", sa.Numeric(18, 8), nullable=True),
        sa.Column("drawdown_pct", sa.Numeric(10, 6), nullable=True),
        sa.Column("benchmark_return_pct", sa.Numeric(10, 6), nullable=True),
    )
    op.create_index("ix_portfolio_snapshots_timestamp", "portfolio_snapshots", ["timestamp"])

    # --- agent_events (append-only audit log) ---
    op.create_table(
        "agent_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("timestamp", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("proposal_id", UUID, sa.ForeignKey("proposals.id"), nullable=True),
    )
    op.create_index("ix_agent_events_type_time", "agent_events", ["event_type", "timestamp"])
    op.create_index("ix_agent_events_agent_time", "agent_events", ["agent_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("agent_events")
    op.drop_table("portfolio_snapshots")
    op.drop_table("positions")
    op.drop_table("orders")
    op.drop_table("human_decisions")
    op.drop_table("critic_reviews")
    op.drop_table("proposals")
    op.drop_table("users")