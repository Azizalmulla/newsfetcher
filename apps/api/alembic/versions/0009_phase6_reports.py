"""Draft/final reports, versions, branding.

Revision ID: 0009_phase6_reports
Revises: 0008_phase5_semantic
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_phase6_reports"
down_revision: Union[str, None] = "0008_phase5_semantic"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_branding",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("primary_color", sa.String(length=16), nullable=False, server_default="#0B3D2E"),
        sa.Column("accent_color", sa.String(length=16), nullable=False, server_default="#C4A35A"),
        sa.Column("footer_text", sa.Text(), nullable=True),
        sa.Column("logo_storage_key", sa.String(length=1024), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"])
    op.create_index("ix_reports_status", "reports", ["status"])

    op.create_table(
        "report_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("text_match_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("included", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("title_snapshot", sa.String(length=1024), nullable=True),
        sa.Column("source_name_snapshot", sa.String(length=255), nullable=True),
        sa.Column("url_snapshot", sa.String(length=2048), nullable=True),
        sa.Column("snippet_snapshot", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["text_match_id"], ["text_matches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("report_id", "sort_order", name="uq_report_items_report_sort"),
    )
    op.create_index("ix_report_items_report_id", "report_items", ["report_id"])
    op.create_index("ix_report_items_tenant_id", "report_items", ["tenant_id"])

    op.create_table(
        "report_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status_at_version", sa.String(length=32), nullable=False, server_default="final"),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("pdf_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("pdf_sha256", sa.String(length=128), nullable=True),
        sa.Column("pdf_bytes", sa.Integer(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("email_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "email_recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("email_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("report_id", "version_number", name="uq_report_versions_num"),
        sa.UniqueConstraint("report_id", "content_hash", name="uq_report_versions_report_hash"),
    )
    op.create_index("ix_report_versions_report_id", "report_versions", ["report_id"])
    op.create_index("ix_report_versions_tenant_id", "report_versions", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("report_versions")
    op.drop_table("report_items")
    op.drop_table("reports")
    op.drop_table("tenant_branding")
