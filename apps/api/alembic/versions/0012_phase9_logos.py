"""Logo templates, detections, matches, report link.

Revision ID: 0012_phase9_logos
Revises: 0011_phase8_source_closure
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_phase9_logos"
down_revision: Union[str, None] = "0011_phase8_source_closure"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_logo_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("variant", sa.String(length=64), nullable=False, server_default="primary"),
        sa.Column("track_role", sa.String(length=32), nullable=False, server_default="own"),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_type", sa.String(length=128), nullable=False, server_default="image/png"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("min_confidence", sa.Float(), nullable=False, server_default="0.72"),
        sa.Column("feature_fingerprint", sa.String(length=128), nullable=True),
        sa.Column(
            "metadata",
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "content_hash", name="uq_tenant_logo_templates_hash"),
    )
    op.create_index("ix_tenant_logo_templates_tenant_id", "tenant_logo_templates", ["tenant_id"])
    op.create_index("ix_tenant_logo_templates_entity_id", "tenant_logo_templates", ["entity_id"])

    op.create_table(
        "logo_detections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("article_image_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False, server_default="local_screen"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("bbox_x", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("bbox_y", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("bbox_w", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("bbox_h", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("crop_storage_key", sa.String(length=1024), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "raw",
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["page_id"], ["epaper_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["article_image_id"], ["article_images.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_logo_detections_tenant_id", "logo_detections", ["tenant_id"])
    op.create_index("ix_logo_detections_page_id", "logo_detections", ["page_id"])
    op.create_index("ix_logo_detections_article_image_id", "logo_detections", ["article_image_id"])

    op.create_table(
        "logo_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("detection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("match_stage", sa.String(length=64), nullable=False, server_default="local_screen"),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["template_id"], ["tenant_logo_templates.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["detection_id"], ["logo_detections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "tenant_id", "template_id", "detection_id", name="uq_logo_matches_pair"
        ),
    )
    op.create_index("ix_logo_matches_tenant_id", "logo_matches", ["tenant_id"])
    op.create_index("ix_logo_matches_template_id", "logo_matches", ["template_id"])
    op.create_index("ix_logo_matches_detection_id", "logo_matches", ["detection_id"])
    op.create_index("ix_logo_matches_entity_id", "logo_matches", ["entity_id"])
    op.create_index("ix_logo_matches_status", "logo_matches", ["status"])

    op.add_column(
        "report_items",
        sa.Column("logo_match_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_report_items_logo_match_id",
        "report_items",
        "logo_matches",
        ["logo_match_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_report_items_logo_match_id", "report_items", type_="foreignkey")
    op.drop_column("report_items", "logo_match_id")
    op.drop_table("logo_matches")
    op.drop_table("logo_detections")
    op.drop_table("tenant_logo_templates")
