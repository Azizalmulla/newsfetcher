"""Tenant users and monitoring entity tables.

Revision ID: 0005_phase2_tenancy_monitoring
Revises: 0004_observability_jobs
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase2_tenancy_monitoring"
down_revision: Union[str, None] = "0004_observability_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_tenant_users_tenant_email"),
    )
    op.create_index("ix_tenant_users_tenant_id", "tenant_users", ["tenant_id"])
    op.create_index("ix_tenant_users_email", "tenant_users", ["email"])

    op.create_table(
        "monitoring_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_monitoring_groups_tenant_name"),
    )
    op.create_index("ix_monitoring_groups_tenant_id", "monitoring_groups", ["tenant_id"])

    op.create_table(
        "monitoring_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_name_ar", sa.String(length=255), nullable=True),
        sa.Column("canonical_name_en", sa.String(length=255), nullable=True),
        sa.Column("language_preference", sa.String(length=16), nullable=False, server_default="both"),
        sa.Column("semantic_instruction", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["monitoring_groups.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_monitoring_entities_tenant_id", "monitoring_entities", ["tenant_id"])
    op.create_index(
        "ix_monitoring_entities_tenant_type",
        "monitoring_entities",
        ["tenant_id", "entity_type"],
    )

    op.create_table(
        "monitoring_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias_text", sa.String(length=512), nullable=False),
        sa.Column("alias_normalized", sa.String(length=512), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("exact_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "entity_id", "alias_normalized", name="uq_monitoring_aliases_norm"
        ),
    )
    op.create_index("ix_monitoring_aliases_tenant_id", "monitoring_aliases", ["tenant_id"])
    op.create_index("ix_monitoring_aliases_entity_id", "monitoring_aliases", ["entity_id"])

    op.create_table(
        "monitoring_exclusions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("phrase", sa.String(length=512), nullable=False),
        sa.Column("phrase_normalized", sa.String(length=512), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False, server_default="both"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "entity_id", "phrase_normalized", name="uq_monitoring_exclusions_norm"
        ),
    )
    op.create_index("ix_monitoring_exclusions_tenant_id", "monitoring_exclusions", ["tenant_id"])
    op.create_index("ix_monitoring_exclusions_entity_id", "monitoring_exclusions", ["entity_id"])


def downgrade() -> None:
    op.drop_index("ix_monitoring_exclusions_entity_id", table_name="monitoring_exclusions")
    op.drop_index("ix_monitoring_exclusions_tenant_id", table_name="monitoring_exclusions")
    op.drop_table("monitoring_exclusions")
    op.drop_index("ix_monitoring_aliases_entity_id", table_name="monitoring_aliases")
    op.drop_index("ix_monitoring_aliases_tenant_id", table_name="monitoring_aliases")
    op.drop_table("monitoring_aliases")
    op.drop_index("ix_monitoring_entities_tenant_type", table_name="monitoring_entities")
    op.drop_index("ix_monitoring_entities_tenant_id", table_name="monitoring_entities")
    op.drop_table("monitoring_entities")
    op.drop_index("ix_monitoring_groups_tenant_id", table_name="monitoring_groups")
    op.drop_table("monitoring_groups")
    op.drop_index("ix_tenant_users_email", table_name="tenant_users")
    op.drop_index("ix_tenant_users_tenant_id", table_name="tenant_users")
    op.drop_table("tenant_users")
