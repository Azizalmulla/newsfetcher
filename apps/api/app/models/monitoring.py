from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MonitoringGroup(Base):
    __tablename__ = "monitoring_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_monitoring_groups_tenant_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MonitoringEntity(Base):
    __tablename__ = "monitoring_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("monitoring_groups.id", ondelete="SET NULL"), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    canonical_name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_preference: Mapped[str] = mapped_column(String(16), nullable=False, default="both")
    semantic_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    aliases: Mapped[list[MonitoringAlias]] = relationship(back_populates="entity")
    exclusions: Mapped[list[MonitoringExclusion]] = relationship(back_populates="entity")


class MonitoringAlias(Base):
    __tablename__ = "monitoring_aliases"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "entity_id", "alias_normalized", name="uq_monitoring_aliases_norm"
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
    alias_text: Mapped[str] = mapped_column(String(512), nullable=False)
    alias_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    exact_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity: Mapped[MonitoringEntity] = relationship(back_populates="aliases")


class MonitoringExclusion(Base):
    __tablename__ = "monitoring_exclusions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "entity_id", "phrase_normalized", name="uq_monitoring_exclusions_norm"
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
    phrase: Mapped[str] = mapped_column(String(512), nullable=False)
    phrase_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="both")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entity: Mapped[MonitoringEntity] = relationship(back_populates="exclusions")
