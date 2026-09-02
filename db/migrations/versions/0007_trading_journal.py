"""Hash-chained trading journal.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None

JSONB = pg.JSONB()
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "trading_journal",
        sa.Column("id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("timestamp", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_trading_journal_seq", "trading_journal", ["seq"])
    op.create_index("ix_trading_journal_kind", "trading_journal", ["kind", "timestamp"])
    op.create_index("ix_trading_journal_symbol", "trading_journal", ["symbol", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_trading_journal_symbol", table_name="trading_journal")
    op.drop_index("ix_trading_journal_kind", table_name="trading_journal")
    op.drop_index("ix_trading_journal_seq", table_name="trading_journal")
    op.drop_table("trading_journal")
