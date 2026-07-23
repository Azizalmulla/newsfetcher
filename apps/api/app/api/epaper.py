from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, get_current_auth, require_roles
from app.db.session import get_db
from app.models.epaper import Cutting, EpaperEdition, OcrBlock
from app.models.sources import Publisher, SourceChannel
from app.services import epaper as epaper_service

router = APIRouter(prefix="/epaper", tags=["epaper"])


class BlockOut(BaseModel):
    id: UUID
    block_index: int
    text: str
    source: str
    confidence: float
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float


class PageOut(BaseModel):
    id: UUID
    page_number: int
    status: str
    text_layer_chars: int
    ocr_provider: str | None
    ocr_model: str | None
    full_text: str | None
    blocks: list[BlockOut]


class EditionOut(BaseModel):
    id: UUID
    publisher_id: UUID
    source_channel_id: UUID
    edition_date: date
    title: str | None
    status: str
    pdf_sha256: str | None
    pdf_bytes: int | None
    page_count: int
    ingest_mode: str
    pages: list[PageOut]


class CuttingOut(BaseModel):
    id: UUID
    page_id: UUID
    entity_id: UUID | None
    status: str
    match_type: str
    matched_term: str
    score: float
    title: str | None
    body_text: str
    bbox_x: float
    bbox_y: float
    bbox_w: float
    bbox_h: float
    reviewer_note: str | None
    reviewed_at: datetime | None


class CuttingDecisionIn(BaseModel):
    status: str = Field(pattern=r"^(proposed|included|excluded|adjusted)$")
    note: str | None = None
    body_text: str | None = None
    bbox: dict[str, float] | None = None


def _block_out(block: OcrBlock) -> BlockOut:
    return BlockOut(
        id=block.id,
        block_index=block.block_index,
        text=block.text,
        source=block.source,
        confidence=block.confidence,
        bbox_x=block.bbox_x,
        bbox_y=block.bbox_y,
        bbox_w=block.bbox_w,
        bbox_h=block.bbox_h,
    )


def _edition_out(edition: EpaperEdition) -> EditionOut:
    pages = sorted(edition.pages, key=lambda row: row.page_number)
    return EditionOut(
        id=edition.id,
        publisher_id=edition.publisher_id,
        source_channel_id=edition.source_channel_id,
        edition_date=edition.edition_date,
        title=edition.title,
        status=edition.status,
        pdf_sha256=edition.pdf_sha256,
        pdf_bytes=edition.pdf_bytes,
        page_count=edition.page_count,
        ingest_mode=edition.ingest_mode,
        pages=[
            PageOut(
                id=page.id,
                page_number=page.page_number,
                status=page.status,
                text_layer_chars=page.text_layer_chars,
                ocr_provider=page.ocr_provider,
                ocr_model=page.ocr_model,
                full_text=page.full_text,
                blocks=[_block_out(b) for b in sorted(page.blocks, key=lambda x: x.block_index)],
            )
            for page in pages
        ],
    )


def _cutting_out(cutting: Cutting) -> CuttingOut:
    return CuttingOut(
        id=cutting.id,
        page_id=cutting.page_id,
        entity_id=cutting.entity_id,
        status=cutting.status,
        match_type=cutting.match_type,
        matched_term=cutting.matched_term,
        score=cutting.score,
        title=cutting.title,
        body_text=cutting.body_text,
        bbox_x=cutting.bbox_x,
        bbox_y=cutting.bbox_y,
        bbox_w=cutting.bbox_w,
        bbox_h=cutting.bbox_h,
        reviewer_note=cutting.reviewer_note,
        reviewed_at=cutting.reviewed_at,
    )


@router.get("/editions", response_model=list[EditionOut])
def list_editions(
    channel_id: UUID | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[EditionOut]:
    _ = auth
    return [
        _edition_out(row)
        for row in epaper_service.list_editions(db, channel_id=channel_id)
    ]


@router.get("/editions/{edition_id}", response_model=EditionOut)
def get_edition(
    edition_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> EditionOut:
    _ = auth
    try:
        return _edition_out(epaper_service.get_edition(db, edition_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Edition not found") from exc


@router.post("/editions/upload", response_model=EditionOut, status_code=201)
async def upload_edition(
    channel_id: UUID = Form(...),
    edition_date: date = Form(...),
    title: str | None = Form(default=None),
    source_url: str | None = Form(default=None),
    # Fixture/licensed uploads only. Live discovery remains separately gated.
    allow_ungated_fixture: bool = Form(default=False),
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer", "platform_admin")),
    db: Session = Depends(get_db),
) -> EditionOut:
    pdf_bytes = await file.read()
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Upload must be a PDF")
    # Only platform_admin may bypass legal gate, and only for offline fixtures.
    require_gate = True
    if allow_ungated_fixture:
        if auth.role_code != "platform_admin":
            raise HTTPException(
                status_code=403,
                detail="Only platform_admin may upload ungated fixture editions",
            )
        require_gate = False
    try:
        edition = epaper_service.ingest_edition_pdf(
            db,
            channel_id=channel_id,
            edition_date=edition_date,
            pdf_bytes=pdf_bytes,
            actor_id=auth.user.id,
            title=title,
            source_url=source_url,
            require_legal_gate=require_gate,
            ingest_mode="upload_fixture" if not require_gate else "upload",
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return _edition_out(edition)


@router.post("/editions/{edition_id}/match", response_model=dict)
def match_edition(
    edition_id: UUID,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return epaper_service.propose_cuttings_for_tenant(
            db, tenant_id=auth.tenant_id, edition_id=edition_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Edition not found") from exc


@router.get("/cuttings", response_model=list[CuttingOut])
def list_cuttings(
    edition_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[CuttingOut]:
    rows = epaper_service.list_cuttings(
        db, tenant_id=auth.tenant_id, edition_id=edition_id, status=status
    )
    return [_cutting_out(row) for row in rows]


@router.post("/cuttings/{cutting_id}/decision", response_model=CuttingOut)
def decide_cutting(
    cutting_id: UUID,
    payload: CuttingDecisionIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> CuttingOut:
    try:
        cutting = epaper_service.set_cutting_decision(
            db,
            tenant_id=auth.tenant_id,
            cutting_id=cutting_id,
            actor_id=auth.user.id,
            status=payload.status,
            note=payload.note,
            bbox=payload.bbox,
            body_text=payload.body_text,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Cutting not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _cutting_out(cutting)


@router.get("/channels")
def list_epaper_channels(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    _ = auth
    channels = db.scalars(
        select(SourceChannel).where(SourceChannel.code.like("epaper%"))
    ).all()
    out: list[dict[str, object]] = []
    for channel in channels:
        publisher = db.get(Publisher, channel.publisher_id)
        out.append(
            {
                "id": str(channel.id),
                "code": channel.code,
                "label": channel.label,
                "publisher": publisher.name_en if publisher else None,
                "is_active": channel.is_active,
            }
        )
    return out
