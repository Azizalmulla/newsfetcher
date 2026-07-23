"""Source registry tables.

Revision ID: 0003_source_registry
Revises: 0002_tenancy_skeleton
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_source_registry"
down_revision: Union[str, None] = "0002_tenancy_skeleton"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publishers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("homepage_url", sa.String(length=512), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False, server_default="KW"),
        sa.Column("media_type", sa.String(length=64), nullable=False, server_default="newspaper"),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("code", name="uq_publishers_code"),
    )

    op.create_table(
        "source_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("publisher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.ForeignKeyConstraint(["publisher_id"], ["publishers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("publisher_id", "code", name="uq_source_channels_publisher_code"),
    )
    op.create_index("ix_source_channels_publisher_id", "source_channels", ["publisher_id"])

    op.create_table(
        "source_assessments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=64),
            nullable=False,
            server_default="pending_assessment",
        ),
        sa.Column("robots_txt_url", sa.String(length=512), nullable=True),
        sa.Column(
            "robots_allows_fetch", sa.String(length=32), nullable=False, server_default="unknown"
        ),
        sa.Column("terms_url", sa.String(length=512), nullable=True),
        sa.Column(
            "commercial_reuse", sa.String(length=32), nullable=False, server_default="unknown"
        ),
        sa.Column("rss_available", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column(
            "public_api_available", sa.String(length=32), nullable=False, server_default="unknown"
        ),
        sa.Column(
            "sitemap_available", sa.String(length=32), nullable=False, server_default="unknown"
        ),
        sa.Column(
            "epaper_available", sa.String(length=32), nullable=False, server_default="unknown"
        ),
        sa.Column(
            "auth_paywall_status", sa.String(length=32), nullable=False, server_default="unknown"
        ),
        sa.Column(
            "copyright_licensing_risk",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "recommended_connector", sa.String(length=64), nullable=False, server_default="pending"
        ),
        sa.Column("legal_gate", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "assessment_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["source_channel_id"], ["source_channels.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_channel_id", name="uq_source_assessments_channel"),
    )

    op.create_table(
        "source_connector_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "connector_type", sa.String(length=64), nullable=False, server_default="pending"
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("politeness_delay_ms", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("max_requests_per_minute", sa.Integer(), nullable=False, server_default="10"),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(["source_channel_id"], ["source_channels.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_channel_id", name="uq_source_connector_configs_channel"),
    )

    op.create_table(
        "source_fetch_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_fetched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column(
            "meta",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_channel_id"], ["source_channels.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_source_fetch_runs_source_channel_id", "source_fetch_runs", ["source_channel_id"]
    )

    op.create_table(
        "source_failures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fetch_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("failure_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_channel_id"], ["source_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fetch_run_id"], ["source_fetch_runs.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_source_failures_source_channel_id", "source_failures", ["source_channel_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_source_failures_source_channel_id", table_name="source_failures")
    op.drop_table("source_failures")
    op.drop_index("ix_source_fetch_runs_source_channel_id", table_name="source_fetch_runs")
    op.drop_table("source_fetch_runs")
    op.drop_table("source_connector_configs")
    op.drop_table("source_assessments")
    op.drop_index("ix_source_channels_publisher_id", table_name="source_channels")
    op.drop_table("source_channels")
    op.drop_table("publishers")
