"""Text matches and match evidence.

Revision ID: 0007_phase4_matching
Revises: 0006_phase3_articles
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_phase4_matching"
down_revision: Union[str, None] = "0006_phase3_articles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "text_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column("best_match_type", sa.String(length=64), nullable=False),
        sa.Column("best_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("matched_term", sa.String(length=512), nullable=False),
        sa.Column("matched_term_normalized", sa.String(length=512), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "entity_id", "article_id", name="uq_text_matches_tenant_entity_article"
        ),
    )
    op.create_index("ix_text_matches_tenant_id", "text_matches", ["tenant_id"])
    op.create_index("ix_text_matches_tenant_status", "text_matches", ["tenant_id", "status"])
    op.create_index("ix_text_matches_entity_id", "text_matches", ["entity_id"])
    op.create_index("ix_text_matches_article_id", "text_matches", ["article_id"])

    op.create_table(
        "match_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("text_match_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_type", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("surface_form", sa.String(length=512), nullable=False),
        sa.Column("normalized_form", sa.String(length=512), nullable=False),
        sa.Column("field_name", sa.String(length=64), nullable=False, server_default="body"),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("evidence_span", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["text_match_id"], ["text_matches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_match_evidence_text_match_id", "match_evidence", ["text_match_id"])
    op.create_index("ix_match_evidence_tenant_id", "match_evidence", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_match_evidence_tenant_id", table_name="match_evidence")
    op.drop_index("ix_match_evidence_text_match_id", table_name="match_evidence")
    op.drop_table("match_evidence")
    op.drop_index("ix_text_matches_article_id", table_name="text_matches")
    op.drop_index("ix_text_matches_entity_id", table_name="text_matches")
    op.drop_index("ix_text_matches_tenant_status", table_name="text_matches")
    op.drop_index("ix_text_matches_tenant_id", table_name="text_matches")
    op.drop_table("text_matches")
