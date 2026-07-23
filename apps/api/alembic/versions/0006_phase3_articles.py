"""Articles, versions, images, story clusters.

Revision ID: 0006_phase3_articles
Revises: 0005_phase2_tenancy_monitoring
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_phase3_articles"
down_revision: Union[str, None] = "0005_phase2_tenancy_monitoring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "story_clusters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("representative_title", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_story_clusters_title_fingerprint", "story_clusters", ["title_fingerprint"])

    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("publisher_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("subtitle", sa.String(length=1024), nullable=True),
        sa.Column("author", sa.String(length=512), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_source", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=False),
        sa.Column("body_original", sa.Text(), nullable=True),
        sa.Column("body_normalized", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("title_hash", sa.String(length=128), nullable=True),
        sa.Column("normalized_url", sa.String(length=2048), nullable=False),
        sa.Column("story_cluster_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["publisher_id"], ["publishers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_channel_id"], ["source_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["story_cluster_id"], ["story_clusters.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "source_channel_id", "canonical_url", name="uq_articles_channel_canonical_url"
        ),
    )
    op.create_index("ix_articles_publisher_id", "articles", ["publisher_id"])
    op.create_index("ix_articles_source_channel_id", "articles", ["source_channel_id"])
    op.create_index("ix_articles_content_hash", "articles", ["content_hash"])
    op.create_index("ix_articles_normalized_url", "articles", ["normalized_url"])

    op.create_table(
        "article_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("body_original", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "raw_snapshot",
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
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("article_id", "version_number", name="uq_article_versions_num"),
    )

    op.create_table(
        "article_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=True),
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
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_article_images_article_id", "article_images", ["article_id"])

    op.create_table(
        "story_cluster_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("story_cluster_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["story_cluster_id"], ["story_clusters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("article_id", name="uq_story_cluster_members_article"),
    )


def downgrade() -> None:
    op.drop_table("story_cluster_members")
    op.drop_index("ix_article_images_article_id", table_name="article_images")
    op.drop_table("article_images")
    op.drop_table("article_versions")
    op.drop_index("ix_articles_normalized_url", table_name="articles")
    op.drop_index("ix_articles_content_hash", table_name="articles")
    op.drop_index("ix_articles_source_channel_id", table_name="articles")
    op.drop_index("ix_articles_publisher_id", table_name="articles")
    op.drop_table("articles")
    op.drop_index("ix_story_clusters_title_fingerprint", table_name="story_clusters")
    op.drop_table("story_clusters")
