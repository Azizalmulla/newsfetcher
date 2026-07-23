"""E-paper editions, OCR blocks, cuttings, report cutting link.

Revision ID: 0010_phase7_epaper
Revises: 0009_phase6_reports
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_phase7_epaper"
down_revision: Union[str, None] = "0009_phase6_reports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "epaper_editions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("publisher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edition_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="discovered"),
        sa.Column("pdf_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("pdf_sha256", sa.String(length=128), nullable=True),
        sa.Column("pdf_bytes", sa.Integer(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingest_mode", sa.String(length=32), nullable=False, server_default="upload"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["publisher_id"], ["publishers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_channel_id"], ["source_channels.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "source_channel_id", "edition_date", name="uq_epaper_editions_channel_date"
        ),
    )
    op.create_index("ix_epaper_editions_publisher_id", "epaper_editions", ["publisher_id"])
    op.create_index("ix_epaper_editions_source_channel_id", "epaper_editions", ["source_channel_id"])
    op.create_index("ix_epaper_editions_status", "epaper_editions", ["status"])

    op.create_table(
        "epaper_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("edition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("text_layer_chars", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ocr_provider", sa.String(length=64), nullable=True),
        sa.Column("ocr_model", sa.String(length=128), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("render_storage_key", sa.String(length=1024), nullable=True),
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
        sa.ForeignKeyConstraint(["edition_id"], ["epaper_editions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("edition_id", "page_number", name="uq_epaper_pages_edition_page"),
    )
    op.create_index("ix_epaper_pages_edition_id", "epaper_pages", ["edition_id"])

    op.create_table(
        "ocr_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("block_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="text_layer"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("bbox_x", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("bbox_y", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("bbox_w", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("bbox_h", sa.Float(), nullable=False, server_default="1.0"),
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
        sa.ForeignKeyConstraint(["page_id"], ["epaper_pages.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ocr_blocks_page_id", "ocr_blocks", ["page_id"])

    op.create_table(
        "cuttings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("match_type", sa.String(length=64), nullable=False, server_default="exact"),
        sa.Column("matched_term", sa.String(length=512), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("bbox_x", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("bbox_y", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("bbox_w", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("bbox_h", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("image_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "evidence",
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
        sa.ForeignKeyConstraint(["page_id"], ["epaper_pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_cuttings_tenant_id", "cuttings", ["tenant_id"])
    op.create_index("ix_cuttings_page_id", "cuttings", ["page_id"])
    op.create_index("ix_cuttings_entity_id", "cuttings", ["entity_id"])
    op.create_index("ix_cuttings_status", "cuttings", ["status"])

    op.add_column(
        "report_items",
        sa.Column("cutting_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_report_items_cutting_id",
        "report_items",
        "cuttings",
        ["cutting_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_report_items_cutting_id", "report_items", type_="foreignkey")
    op.drop_column("report_items", "cutting_id")
    op.drop_table("cuttings")
    op.drop_table("ocr_blocks")
    op.drop_table("epaper_pages")
    op.drop_table("epaper_editions")
