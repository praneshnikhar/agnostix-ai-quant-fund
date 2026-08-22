"""Fundamental intelligence schema: company_profiles, financial_metrics,
financial_statements, earnings_events, valuation_snapshots,
research_documents, research_runs, research_feedback.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None

UUID = pg.UUID(as_uuid=True)
JSONB = pg.JSONB()
TIMESTAMPTZ = sa.DateTime(timezone=True)
DATE = sa.Date()


def upgrade() -> None:
    op.create_table(
        "company_profiles",
        sa.Column("symbol", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("employees", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "financial_metrics",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("metric", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(24, 8), nullable=True),
        sa.Column("period_type", sa.String(16), nullable=False),
        sa.Column("period_end", DATE, nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("units", sa.String(32), nullable=False, server_default="usd"),
        sa.Column("quality", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_record_id", sa.Text(), nullable=True),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_fin_metrics_identity",
        "financial_metrics",
        ["provider", "symbol", "metric", "period_type", "period_end"],
    )
    op.create_index(
        "ix_fin_metrics_symbol_metric", "financial_metrics", ["symbol", "metric", "period_end"]
    )

    op.create_table(
        "financial_statements",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("statement_type", sa.String(16), nullable=False),
        sa.Column("period_type", sa.String(16), nullable=False),
        sa.Column("period_end", DATE, nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("line_items", JSONB, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("units", sa.String(32), nullable=False, server_default="usd"),
        sa.Column("quality", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_record_id", sa.Text(), nullable=True),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_fin_stmts_identity",
        "financial_statements",
        ["provider", "symbol", "statement_type", "period_type", "period_end"],
    )
    op.create_index("ix_fin_stmts_symbol", "financial_statements", ["symbol", "period_end"])

    op.create_table(
        "earnings_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("event_time", TIMESTAMPTZ, nullable=False),
        sa.Column("period_type", sa.String(16), nullable=False),
        sa.Column("period_end", DATE, nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_quarter", sa.Integer(), nullable=True),
        sa.Column("eps_actual", sa.Numeric(18, 8), nullable=True),
        sa.Column("eps_estimate", sa.Numeric(18, 8), nullable=True),
        sa.Column("revenue_actual", sa.Numeric(24, 8), nullable=True),
        sa.Column("revenue_estimate", sa.Numeric(24, 8), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_record_id", sa.Text(), nullable=True),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_earnings_identity",
        "earnings_events",
        ["provider", "symbol", "period_type", "period_end"],
    )
    op.create_index("ix_earnings_symbol_time", "earnings_events", ["symbol", "event_time"])

    op.create_table(
        "valuation_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("as_of", TIMESTAMPTZ, nullable=False),
        sa.Column("price", sa.Numeric(18, 8), nullable=True),
        sa.Column("market_cap", sa.Numeric(24, 8), nullable=True),
        sa.Column("pe_ratio", sa.Numeric(18, 8), nullable=True),
        sa.Column("forward_pe", sa.Numeric(18, 8), nullable=True),
        sa.Column("ps_ratio", sa.Numeric(18, 8), nullable=True),
        sa.Column("ev_ebitda", sa.Numeric(18, 8), nullable=True),
        sa.Column("fcf_yield", sa.Numeric(18, 8), nullable=True),
        sa.Column("shares_outstanding", sa.Numeric(24, 8), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("received_at", TIMESTAMPTZ, nullable=False),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_valuation_symbol_asof", "valuation_snapshots", ["symbol", "as_of"])

    op.create_table(
        "research_documents",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("document_id", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("published_at", TIMESTAMPTZ, nullable=False),
        sa.Column("retrieved_at", TIMESTAMPTZ, nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("stored_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_research_docs_identity", "research_documents", ["provider", "document_id"]
    )
    op.create_index(
        "ix_research_docs_symbol_pub", "research_documents", ["symbol", "published_at"]
    )

    op.create_table(
        "research_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", TIMESTAMPTZ, nullable=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("parent_run_id", UUID, nullable=True),
        sa.Column("context_version", sa.Text(), nullable=False, server_default="v0"),
        sa.Column("context_payload", JSONB, nullable=True),
        sa.Column("agent_id", sa.Text(), nullable=True),
        sa.Column("agent_version", sa.Text(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("model_provider", sa.Text(), nullable=True),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("research_output", JSONB, nullable=True),
        sa.Column("critic_output", JSONB, nullable=True),
        sa.Column("critic_verdict", sa.String(16), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_research_runs_created_at", "research_runs", ["created_at"])
    op.create_index("ix_research_runs_status", "research_runs", ["status"])
    op.create_index("ix_research_runs_verdict", "research_runs", ["critic_verdict"])
    op.create_index(
        "ix_research_runs_symbol_created", "research_runs", ["symbol", "created_at"]
    )

    op.create_table(
        "research_feedback",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("research_runs.id"),
            nullable=False,
        ),
        sa.Column("user_id", UUID, nullable=True),
        sa.Column("decision", sa.String(24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("decided_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_research_feedback_run_id", "research_feedback", ["run_id"])


def downgrade() -> None:
    op.drop_table("research_feedback")
    op.drop_table("research_runs")
    op.drop_table("research_documents")
    op.drop_table("valuation_snapshots")
    op.drop_table("earnings_events")
    op.drop_table("financial_statements")
    op.drop_table("financial_metrics")
    op.drop_table("company_profiles")