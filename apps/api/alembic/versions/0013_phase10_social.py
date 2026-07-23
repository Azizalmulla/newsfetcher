"""Social accounts/posts/matches + X integration gates.

Revision ID: 0013_phase10_social
Revises: 0012_phase9_logos
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_phase10_social"
down_revision: Union[str, None] = "0012_phase9_logos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "social_integration_gates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="x"),
        sa.Column("credentials_available", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pricing_reviewed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("endpoints_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("terms_documented", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("cost_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("live_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "checklist",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("platform", name="uq_social_integration_gates_platform"),
    )

    op.create_table(
        "social_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="x"),
        sa.Column("handle", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("external_user_id", sa.String(length=128), nullable=True),
        sa.Column("publisher_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("account_type", sa.String(length=64), nullable=False, server_default="outlet"),
        sa.Column("is_approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.ForeignKeyConstraint(["publisher_id"], ["publishers.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("platform", "handle", name="uq_social_accounts_platform_handle"),
    )
    op.create_index("ix_social_accounts_platform", "social_accounts", ["platform"])

    op.create_table(
        "social_posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="x"),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("external_post_id", sa.String(length=128), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("permalink", sa.String(length=2048), nullable=True),
        sa.Column("ingest_source", sa.String(length=64), nullable=False, server_default="fixture"),
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
        sa.ForeignKeyConstraint(["account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("platform", "external_post_id", name="uq_social_posts_external"),
    )
    op.create_index("ix_social_posts_platform", "social_posts", ["platform"])
    op.create_index("ix_social_posts_account_id", "social_posts", ["account_id"])

    op.create_table(
        "social_matches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="proposed"),
        sa.Column("best_match_type", sa.String(length=64), nullable=False),
        sa.Column("best_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("matched_term", sa.String(length=512), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["social_posts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id", "entity_id", "post_id", name="uq_social_matches_tenant_entity_post"
        ),
    )
    op.create_index("ix_social_matches_tenant_id", "social_matches", ["tenant_id"])
    op.create_index("ix_social_matches_entity_id", "social_matches", ["entity_id"])
    op.create_index("ix_social_matches_post_id", "social_matches", ["post_id"])
    op.create_index("ix_social_matches_status", "social_matches", ["status"])

    op.add_column(
        "report_items",
        sa.Column("social_match_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_report_items_social_match_id",
        "report_items",
        "social_matches",
        ["social_match_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_report_items_social_match_id", "report_items", type_="foreignkey")
    op.drop_column("report_items", "social_match_id")
    op.drop_table("social_matches")
    op.drop_table("social_posts")
    op.drop_table("social_accounts")
    op.drop_table("social_integration_gates")
