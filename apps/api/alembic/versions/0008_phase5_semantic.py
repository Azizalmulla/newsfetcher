"""Semantic embeddings, candidates, relevance decisions.

Revision ID: 0008_phase5_semantic
Revises: 0007_phase4_matching
Create Date: 2026-07-22
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0008_phase5_semantic"
down_revision: Union[str, None] = "0007_phase4_matching"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Keep in sync with Settings.embedding_dimensions default.
EMBED_DIM = 1024


def upgrade() -> None:
    op.create_table(
        "article_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=False),
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
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "article_id", "provider", "model", name="uq_article_embeddings_article_model"
        ),
    )
    op.create_index("ix_article_embeddings_article_id", "article_embeddings", ["article_id"])
    # HNSW works on small/empty tables; skip cleanly if unsupported.
    op.execute(
        """
        DO $$
        BEGIN
          CREATE INDEX IF NOT EXISTS ix_article_embeddings_embedding_hnsw
          ON article_embeddings USING hnsw (embedding vector_cosine_ops);
        EXCEPTION WHEN OTHERS THEN
          RAISE NOTICE 'hnsw index skipped: %', SQLERRM;
        END $$;
        """
    )

    op.create_table(
        "entity_embeddings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=False),
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
        sa.UniqueConstraint(
            "entity_id", "provider", "model", name="uq_entity_embeddings_entity_model"
        ),
    )
    op.create_index("ix_entity_embeddings_tenant_id", "entity_embeddings", ["tenant_id"])
    op.create_index("ix_entity_embeddings_entity_id", "entity_embeddings", ["entity_id"])

    op.create_table(
        "semantic_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vector_similarity", sa.Float(), nullable=False),
        sa.Column("rerank_score", sa.Float(), nullable=True),
        sa.Column("lexical_best_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("classifier_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("classifier_label", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_review"),
        sa.Column(
            "provenance",
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
        sa.ForeignKeyConstraint(["entity_id"], ["monitoring_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "tenant_id",
            "entity_id",
            "article_id",
            name="uq_semantic_candidates_tenant_entity_article",
        ),
    )
    op.create_index("ix_semantic_candidates_tenant_id", "semantic_candidates", ["tenant_id"])
    op.create_index(
        "ix_semantic_candidates_tenant_status", "semantic_candidates", ["tenant_id", "status"]
    )

    op.create_table(
        "relevance_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("semantic_candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False, server_default="v1"),
        sa.Column("prompt_version", sa.String(length=32), nullable=False, server_default="rules_v1"),
        sa.Column(
            "features",
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
        sa.ForeignKeyConstraint(
            ["semantic_candidate_id"], ["semantic_candidates.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_relevance_decisions_tenant_id", "relevance_decisions", ["tenant_id"])

    op.create_table(
        "tenant_match_thresholds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("min_cosine", sa.Float(), nullable=False),
        sa.Column("min_rerank", sa.Float(), nullable=False),
        sa.Column("min_classifier", sa.Float(), nullable=False, server_default="0.6"),
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
        sa.UniqueConstraint("tenant_id", name="uq_tenant_match_thresholds_tenant"),
    )


def downgrade() -> None:
    op.drop_table("tenant_match_thresholds")
    op.drop_index("ix_relevance_decisions_tenant_id", table_name="relevance_decisions")
    op.drop_table("relevance_decisions")
    op.drop_index("ix_semantic_candidates_tenant_status", table_name="semantic_candidates")
    op.drop_index("ix_semantic_candidates_tenant_id", table_name="semantic_candidates")
    op.drop_table("semantic_candidates")
    op.drop_index("ix_entity_embeddings_entity_id", table_name="entity_embeddings")
    op.drop_index("ix_entity_embeddings_tenant_id", table_name="entity_embeddings")
    op.drop_table("entity_embeddings")
    op.execute("DROP INDEX IF EXISTS ix_article_embeddings_embedding_hnsw")
    op.drop_index("ix_article_embeddings_article_id", table_name="article_embeddings")
    op.drop_table("article_embeddings")
