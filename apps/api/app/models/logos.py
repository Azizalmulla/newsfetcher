from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TenantLogoTemplate(Base):
    __tablename__ = "tenant_logo_templates"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "content_hash", name="uq_tenant_logo_templates_hash"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitoring_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    variant: Mapped[str] = mapped_column(String(64), nullable=False, default="primary")
    # own|competitor|other tracked via track_role
    track_role: Mapped[str] = mapped_column(String(32), nullable=False, default="own")
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False, default="image/png")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.72)
    feature_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    matches: Mapped[list[LogoMatch]] = relationship(back_populates="template")


class LogoDetection(Base):
    """Raw detector candidates on a page or article image (pre-match)."""

    __tablename__ = "logo_detections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("epaper_pages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    article_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("article_images.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False, default="local_screen")
    # local_screen|embedding_similarity|region_verify|external_verify
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox_w: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    bbox_h: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)
    crop_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    matches: Mapped[list[LogoMatch]] = relationship(back_populates="detection")


class LogoMatch(Base):
    """Proposed template↔detection link. Never auto-finalized."""

    __tablename__ = "logo_matches"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "template_id", "detection_id", name="uq_logo_matches_pair"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_logo_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    detection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("logo_detections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitoring_entities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed", index=True)
    # proposed|included|excluded|adjusted
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    match_stage: Mapped[str] = mapped_column(String(64), nullable=False, default="local_screen")
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

    template: Mapped[TenantLogoTemplate] = relationship(back_populates="matches")
    detection: Mapped[LogoDetection] = relationship(back_populates="matches")
