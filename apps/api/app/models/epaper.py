from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
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


class EpaperEdition(Base):
    __tablename__ = "epaper_editions"
    __table_args__ = (
        UniqueConstraint(
            "source_channel_id", "edition_date", name="uq_epaper_editions_channel_date"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publisher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publishers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edition_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="discovered", index=True
    )
    pdf_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    pdf_sha256: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pdf_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ingest_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="upload")
    # upload|licensed_download — never live-scrape without legal gate
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    pages: Mapped[list[EpaperPage]] = relationship(
        back_populates="edition", order_by="EpaperPage.page_number"
    )


class EpaperPage(Base):
    __tablename__ = "epaper_pages"
    __table_args__ = (
        UniqueConstraint("edition_id", "page_number", name="uq_epaper_pages_edition_page"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("epaper_editions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    width: Mapped[float | None] = mapped_column(Float, nullable=True)
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    text_layer_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ocr_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ocr_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    render_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    edition: Mapped[EpaperEdition] = relationship(back_populates="pages")
    blocks: Mapped[list[OcrBlock]] = relationship(
        back_populates="page", order_by="OcrBlock.block_index"
    )
    cuttings: Mapped[list[Cutting]] = relationship(back_populates="page")


class OcrBlock(Base):
    __tablename__ = "ocr_blocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("epaper_pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="text_layer")
    # text_layer|mistral|local_stub
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    bbox_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox_w: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    bbox_h: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    page: Mapped[EpaperPage] = relationship(back_populates="blocks")


class Cutting(Base):
    __tablename__ = "cuttings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("epaper_pages.id", ondelete="CASCADE"),
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
    match_type: Mapped[str] = mapped_column(String(64), nullable=False, default="exact")
    matched_term: Mapped[str] = mapped_column(String(512), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    body_text: Mapped[str] = mapped_column(Text, nullable=False)
    bbox_x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox_y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox_w: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    bbox_h: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    image_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    page: Mapped[EpaperPage] = relationship(back_populates="cuttings")
