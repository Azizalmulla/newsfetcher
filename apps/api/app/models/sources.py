from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
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
from app.models.enums import (
    ChannelLanguage,
    ConnectorMethod,
    LegalGate,
    SourceAssessmentStatus,
)


class Publisher(Base):
    __tablename__ = "publishers"
    __table_args__ = (UniqueConstraint("code", name="uq_publishers_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    homepage_url: Mapped[str] = mapped_column(String(512), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False, default="KW")
    media_type: Mapped[str] = mapped_column(String(64), nullable=False, default="newspaper")
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    channels: Mapped[list[SourceChannel]] = relationship(back_populates="publisher")


class SourceChannel(Base):
    __tablename__ = "source_channels"
    __table_args__ = (
        UniqueConstraint("publisher_id", "code", name="uq_source_channels_publisher_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publisher_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("publishers.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[ChannelLanguage] = mapped_column(String(8), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    publisher: Mapped[Publisher] = relationship(back_populates="channels")
    assessment: Mapped[SourceAssessment | None] = relationship(
        back_populates="source_channel", uselist=False
    )
    connector_config: Mapped[SourceConnectorConfig | None] = relationship(
        back_populates="source_channel", uselist=False
    )


class SourceAssessment(Base):
    __tablename__ = "source_assessments"
    __table_args__ = (
        UniqueConstraint("source_channel_id", name="uq_source_assessments_channel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[SourceAssessmentStatus] = mapped_column(
        String(64), nullable=False, default=SourceAssessmentStatus.pending_assessment
    )
    robots_txt_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    robots_allows_fetch: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    terms_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    commercial_reuse: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    rss_available: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    public_api_available: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    sitemap_available: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    epaper_available: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    auth_paywall_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    copyright_licensing_risk: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unknown"
    )
    recommended_connector: Mapped[ConnectorMethod] = mapped_column(
        String(64), nullable=False, default=ConnectorMethod.pending
    )
    legal_gate: Mapped[LegalGate] = mapped_column(
        String(32), nullable=False, default=LegalGate.pending
    )
    assessment_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 8 closure: active|blocked|awaiting_licensing|temporarily_broken
    phase8_disposition: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    recovery_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    closure_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    source_channel: Mapped[SourceChannel] = relationship(back_populates="assessment")


class SourceConnectorConfig(Base):
    __tablename__ = "source_connector_configs"
    __table_args__ = (
        UniqueConstraint("source_channel_id", name="uq_source_connector_configs_channel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_type: Mapped[ConnectorMethod] = mapped_column(
        String(64), nullable=False, default=ConnectorMethod.pending
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    politeness_delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    max_requests_per_minute: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    source_channel: Mapped[SourceChannel] = relationship(back_populates="connector_config")


class SourceFetchRun(Base):
    __tablename__ = "source_fetch_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SourceFailure(Base):
    __tablename__ = "source_failures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fetch_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_fetch_runs.id", ondelete="SET NULL"), nullable=True
    )
    failure_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
