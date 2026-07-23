from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, get_current_auth, require_roles
from app.db.session import get_db
from app.models.logos import LogoMatch, TenantLogoTemplate
from app.services import logos as logo_service

router = APIRouter(prefix="/logos", tags=["logos"])


class TemplateOut(BaseModel):
    id: UUID
    label: str
    variant: str
    track_role: str
    entity_id: UUID | None
    content_hash: str
    content_type: str
    byte_size: int
    min_confidence: float
    is_active: bool
    feature_fingerprint: str | None


class DetectionOut(BaseModel):
    id: UUID
    provider: str
    model: str
    stage: str
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    page_id: UUID | None
    article_image_id: UUID | None


class MatchOut(BaseModel):
    id: UUID
    template_id: UUID
    detection_id: UUID
    entity_id: UUID | None
    status: str
    score: float
    match_stage: str
    reviewer_note: str | None
    reviewed_at: datetime | None
    detection: DetectionOut | None = None
    template_label: str | None = None


class DetectIn(BaseModel):
    page_id: UUID | None = None
    article_image_id: UUID | None = None


class DecisionIn(BaseModel):
    status: str = Field(pattern=r"^(proposed|included|excluded|adjusted)$")
    note: str | None = None
    bbox: dict[str, float] | None = None


def _template_out(row: TenantLogoTemplate) -> TemplateOut:
    return TemplateOut(
        id=row.id,
        label=row.label,
        variant=row.variant,
        track_role=row.track_role,
        entity_id=row.entity_id,
        content_hash=row.content_hash,
        content_type=row.content_type,
        byte_size=row.byte_size,
        min_confidence=row.min_confidence,
        is_active=row.is_active,
        feature_fingerprint=row.feature_fingerprint,
    )


def _match_out(row: LogoMatch) -> MatchOut:
    detection = None
    if row.detection is not None:
        detection = DetectionOut(
            id=row.detection.id,
            provider=row.detection.provider,
            model=row.detection.model,
            stage=row.detection.stage,
            confidence=row.detection.confidence,
            bbox_x=row.detection.bbox_x,
            bbox_y=row.detection.bbox_y,
            bbox_w=row.detection.bbox_w,
            bbox_h=row.detection.bbox_h,
            page_id=row.detection.page_id,
            article_image_id=row.detection.article_image_id,
        )
    return MatchOut(
        id=row.id,
        template_id=row.template_id,
        detection_id=row.detection_id,
        entity_id=row.entity_id,
        status=row.status,
        score=row.score,
        match_stage=row.match_stage,
        reviewer_note=row.reviewer_note,
        reviewed_at=row.reviewed_at,
        detection=detection,
        template_label=row.template.label if row.template else None,
    )


@router.post("/templates", response_model=TemplateOut, status_code=201)
async def upload_template(
    label: str = Form(...),
    variant: str = Form(default="primary"),
    track_role: str = Form(default="own"),
    entity_id: UUID | None = Form(default=None),
    min_confidence: float = Form(default=0.72),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> TemplateOut:
    data = await file.read()
    content_type = file.content_type or "image/png"
    try:
        template = logo_service.create_logo_template(
            db,
            tenant_id=auth.tenant_id,
            actor_id=auth.user.id,
            label=label,
            image_bytes=data,
            content_type=content_type,
            entity_id=entity_id,
            variant=variant,
            track_role=track_role,
            min_confidence=min_confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _template_out(template)


@router.get("/templates", response_model=list[TemplateOut])
def get_templates(
    active_only: bool = Query(default=True),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[TemplateOut]:
    return [
        _template_out(row)
        for row in logo_service.list_templates(
            db, tenant_id=auth.tenant_id, active_only=active_only
        )
    ]


@router.post("/detect")
def detect_logos(
    payload: DetectIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return logo_service.run_detect_and_propose(
            db,
            tenant_id=auth.tenant_id,
            actor_id=auth.user.id,
            page_id=payload.page_id,
            article_image_id=payload.article_image_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/matches", response_model=list[MatchOut])
def get_matches(
    status: str | None = Query(default="proposed"),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[MatchOut]:
    return [
        _match_out(row)
        for row in logo_service.list_matches(db, tenant_id=auth.tenant_id, status=status)
    ]


@router.post("/matches/{match_id}/decision", response_model=MatchOut)
def decide_match(
    match_id: UUID,
    payload: DecisionIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> MatchOut:
    try:
        match = logo_service.set_match_decision(
            db,
            tenant_id=auth.tenant_id,
            match_id=match_id,
            actor_id=auth.user.id,
            status=payload.status,
            note=payload.note,
            bbox=payload.bbox,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Logo match not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    loaded = logo_service.list_matches(db, tenant_id=auth.tenant_id, status=None)
    row = next((item for item in loaded if item.id == match.id), match)
    return _match_out(row)
