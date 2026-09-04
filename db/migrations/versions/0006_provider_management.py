"""Provider configuration management with encrypted credential material.

Revision ID: 0006
Revises: 0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0006"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None

UUID = pg.UUID(as_uuid=True)
JSONB = pg.JSONB()
TIMESTAMPTZ = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "provider_configurations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("scope", sa.String(16), nullable=False, server_default="platform"),
        sa.Column("scope_id", UUID, nullable=True),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("last_tested_at", TIMESTAMPTZ, nullable=True),
        sa.Column("connection_status", sa.String(24), nullable=False, server_default="unknown"),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("health_json", JSONB, nullable=True),
        sa.Column("secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("credential_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "uq_provider_config_scope_identity",
        "provider_configurations",
        ["kind", "scope", "scope_id", "provider"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NOT NULL"),
    )
    op.create_index(
        "uq_provider_config_platform_identity",
        "provider_configurations",
        ["kind", "scope", "provider"],
        unique=True,
        postgresql_where=sa.text("scope_id IS NULL"),
    )
    op.create_index(
        "ix_provider_config_kind_provider",
        "provider_configurations",
        ["kind", "provider"],
    )
    op.create_index(
        "ix_provider_config_scope",
        "provider_configurations",
        ["scope", "scope_id"],
    )

    op.create_table(
        "provider_model_configurations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "provider_configuration_id",
            UUID,
            sa.ForeignKey("provider_configurations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("capabilities", JSONB, nullable=True),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(24), nullable=False, server_default="configured"),
        sa.Column("available", sa.Boolean(), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMPTZ, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "uq_provider_model_target",
        "provider_model_configurations",
        ["provider_configuration_id", "provider", "model"],
        unique=True,
    )
    op.create_index(
        "ix_provider_model_provider",
        "provider_model_configurations",
        ["provider", "model"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_model_provider", table_name="provider_model_configurations")
    op.drop_index("uq_provider_model_target", table_name="provider_model_configurations")
    op.drop_table("provider_model_configurations")
    op.drop_index("ix_provider_config_scope", table_name="provider_configurations")
    op.drop_index("ix_provider_config_kind_provider", table_name="provider_configurations")
    op.drop_index("uq_provider_config_platform_identity", table_name="provider_configurations")
    op.drop_index("uq_provider_config_scope_identity", table_name="provider_configurations")
    op.drop_table("provider_configurations")
