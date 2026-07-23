from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SocialIntegrationGate(Base):
    """Singleton-ish per-platform ops gate. Live polling requires all flags true + secrets."""

    __tablename__ = "social_integration_gates"
    __table_args__ = (UniqueConstraint("platform", name="uq_social_integration_gates_platform"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="x")
    credentials_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pricing_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    endpoints_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    terms_documented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cost_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    live_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklist: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SocialAccount(Base):
    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint("platform", "handle", name="uq_social_accounts_platform_handle"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="x", index=True)
    handle: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    publisher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishers.id", ondelete="SET NULL"), nullable=True
    )
    account_type: Mapped[str] = mapped_column(String(64), nullable=False, default="outlet")
    # outlet|official_agency|other — Phase 10 tracks approved outlets only
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    posts: Mapped[list[SocialPost]] = relationship(back_populates="account")


class SocialPost(Base):
    __tablename__ = "social_posts"
    __table_args__ = (
        UniqueConstraint("platform", "external_post_id", name="uq_social_posts_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(String(32), nullable=False, default="x", index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_post_id: Mapped[str] = mapped_column(String(128), nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    permalink: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    ingest_source: Mapped[str] = mapped_column(String(64), nullable=False, default="fixture")
    # fixture|official_api — never scrape
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    account: Mapped[SocialAccount] = relationship(back_populates="posts")
    matches: Mapped[list[SocialMatch]] = relationship(back_populates="post")


class SocialMatch(Base):
    __tablename__ = "social_matches"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "entity_id", "post_id", name="uq_social_matches_tenant_entity_post"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitoring_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("social_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed", index=True)
    best_match_type: Mapped[str] = mapped_column(String(64), nullable=False)
    best_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matched_term: Mapped[str] = mapped_column(String(512), nullable=False)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    post: Mapped[SocialPost] = relationship(back_populates="matches")
