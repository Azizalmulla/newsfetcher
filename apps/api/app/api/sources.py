from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import AuthContext, require_roles
from app.db.session import get_db
from app.models.enums import SourceAssessmentStatus
from app.models.sources import Publisher, SourceAssessment, SourceChannel
from app.services.source_assessment import run_assessments, shortlist_technically_ready
from app.services.source_closure import apply_source_closure, list_source_closure
from app.services.source_health import list_source_health, probe_channel_health

router = APIRouter(prefix="/sources", tags=["sources"])


class AssessmentOut(BaseModel):
    status: str
    legal_gate: str
    recommended_connector: str


class ChannelOut(BaseModel):
    code: str
    label: str
    language: str
    base_url: str
    is_active: bool
    assessment: AssessmentOut | None


class PublisherOut(BaseModel):
    code: str
    name_en: str
    name_ar: str
    homepage_url: str
    media_type: str
    is_mandatory: bool
    channels: list[ChannelOut]


class SourceInventoryOut(BaseModel):
    publisher_count: int
    channel_count: int
    pending_assessment_count: int
    publishers: list[PublisherOut]


def _enum_value(value: Any) -> str:
    return str(value.value if hasattr(value, "value") else value)


@router.get("/inventory", response_model=SourceInventoryOut)
def list_source_inventory(db: Session = Depends(get_db)) -> SourceInventoryOut:
    publishers = db.scalars(
        select(Publisher)
        .options(
            selectinload(Publisher.channels).selectinload(SourceChannel.assessment),
        )
        .order_by(Publisher.name_en)
    ).all()

    pending_count = (
        db.scalar(
            select(func.count())
            .select_from(SourceAssessment)
            .where(SourceAssessment.status == SourceAssessmentStatus.pending_assessment)
        )
        or 0
    )

    channel_count = sum(len(publisher.channels) for publisher in publishers)

    return SourceInventoryOut(
        publisher_count=len(publishers),
        channel_count=channel_count,
        pending_assessment_count=pending_count,
        publishers=[
            PublisherOut(
                code=publisher.code,
                name_en=publisher.name_en,
                name_ar=publisher.name_ar,
                homepage_url=publisher.homepage_url,
                media_type=publisher.media_type,
                is_mandatory=publisher.is_mandatory,
                channels=[
                    ChannelOut(
                        code=channel.code,
                        label=channel.label,
                        language=_enum_value(channel.language),
                        base_url=channel.base_url,
                        is_active=channel.is_active,
                        assessment=(
                            AssessmentOut(
                                status=_enum_value(channel.assessment.status),
                                legal_gate=_enum_value(channel.assessment.legal_gate),
                                recommended_connector=_enum_value(
                                    channel.assessment.recommended_connector
                                ),
                            )
                            if channel.assessment
                            else None
                        ),
                    )
                    for channel in publisher.channels
                ],
            )
            for publisher in publishers
        ],
    )


@router.get("/health")
def source_health_dashboard(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = list_source_health(db)
    return {
        "channel_count": len(rows),
        "enabled_connectors": sum(1 for row in rows if row["connector_enabled"]),
        "channels": rows,
    }


@router.post("/assess")
def assess_all_sources(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Run polite technical assessments for all registered channels."""
    summaries = run_assessments(db, write_docs=True)
    shortlist = shortlist_technically_ready(summaries, limit=4)
    return {
        "assessed": len(summaries),
        "summaries": summaries,
        "technical_shortlist": shortlist,
        "note": (
            "Legal gate remains pending for all sources. "
            "Connectors stay disabled until legal approval."
        ),
    }


@router.post("/health/{publisher_code}/{channel_code}/probe")
def probe_source(
    publisher_code: str,
    channel_code: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    publisher = db.scalar(select(Publisher).where(Publisher.code == publisher_code))
    if publisher is None:
        raise HTTPException(status_code=404, detail="publisher not found")
    channel = db.scalar(
        select(SourceChannel).where(
            SourceChannel.publisher_id == publisher.id,
            SourceChannel.code == channel_code,
        )
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="channel not found")
    return probe_channel_health(db, channel)


@router.get("/closure")
def get_source_closure(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Phase 8 closure dashboard: every mandatory channel must have a disposition."""
    return list_source_closure(db)


@router.post("/closure/apply")
def apply_closure(
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Apply docs/sources/PHASE8_SOURCE_CLOSURE_MATRIX.yaml.

    Never enables connectors or approves legal gates.
    """
    result = apply_source_closure(db, actor_id=str(auth.user.id))
    result["note"] = (
        "Phase 8 closure applied. legal_gate remains pending; connectors stay disabled."
    )
    return result
