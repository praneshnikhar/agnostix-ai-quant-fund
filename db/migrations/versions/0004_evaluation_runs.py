"""Operational model evaluation: evaluation_runs.

One row per multi-model evaluation over a single research context.
Reproduction metadata (context version + hash, prompt/agent versions,
ordered model configuration) is first-class; the full ordered report is
stored as JSONB.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None

UUID = pg.UUID(as_uuid=True)
JSONB = pg.JSONB()
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        # reproducibility metadata (§23)
        sa.Column("context_version", sa.Text(), nullable=False),
        sa.Column("context_hash", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("agent_id", sa.Text(), nullable=True),
        sa.Column("agent_version", sa.Text(), nullable=True),
        sa.Column("models_config", JSONB, nullable=True),
        # outcome
        sa.Column("report", JSONB, nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_evaluation_runs_symbol_created",
        "evaluation_runs",
        ["symbol", "created_at"],
    )
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_symbol_created", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")