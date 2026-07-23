from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, get_current_auth, require_roles
from app.db.session import get_db
from app.models.reports import Report, ReportItem, ReportVersion, TenantBranding
from app.services import reports as report_service
from app.services.storage import get_storage

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportItemOut(BaseModel):
    id: UUID
    sort_order: int
    included: bool
    note: str | None
    text_match_id: UUID | None
    cutting_id: UUID | None
    logo_match_id: UUID | None
    social_match_id: UUID | None
    article_id: UUID | None
    entity_id: UUID | None
    title_snapshot: str | None
    source_name_snapshot: str | None
    url_snapshot: str | None
    snippet_snapshot: str | None


class ReportVersionOut(BaseModel):
    id: UUID
    version_number: int
    status_at_version: str
    content_hash: str
    pdf_storage_key: str | None
    pdf_sha256: str | None
    pdf_bytes: int | None
    email_status: str
    email_recipients: list[str]
    email_error: str | None
    delivered_at: datetime | None
    created_at: datetime


class ReportOut(BaseModel):
    id: UUID
    title: str
    status: str
    period_start: date | None
    period_end: date | None
    notes: str | None
    created_at: datetime
    approved_at: datetime | None
    archived_at: datetime | None
    items: list[ReportItemOut]
    versions: list[ReportVersionOut]


class BrandingOut(BaseModel):
    display_name: str | None
    primary_color: str
    accent_color: str
    footer_text: str | None
    logo_storage_key: str | None


class CreateDraftIn(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    period_start: date | None = None
    period_end: date | None = None
    notes: str | None = None
    match_ids: list[UUID] | None = None
    cutting_ids: list[UUID] | None = None
    include_included_cuttings: bool = True
    logo_match_ids: list[UUID] | None = None
    include_included_logo_matches: bool = True
    social_match_ids: list[UUID] | None = None
    include_included_social_matches: bool = True


class UpdateReportIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    notes: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    status: str | None = Field(default=None, pattern=r"^(draft|in_review)$")


class ReorderIn(BaseModel):
    ordered_item_ids: list[UUID]


class UpdateItemIn(BaseModel):
    note: str | None = None
    included: bool | None = None


class DeliverIn(BaseModel):
    recipients: list[EmailStr] = Field(min_length=1)


class BrandingIn(BaseModel):
    display_name: str | None = None
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    footer_text: str | None = None


def _item_out(item: ReportItem) -> ReportItemOut:
    return ReportItemOut(
        id=item.id,
        sort_order=item.sort_order,
        included=item.included,
        note=item.note,
        text_match_id=item.text_match_id,
        cutting_id=item.cutting_id,
        logo_match_id=item.logo_match_id,
        social_match_id=item.social_match_id,
        article_id=item.article_id,
        entity_id=item.entity_id,
        title_snapshot=item.title_snapshot,
        source_name_snapshot=item.source_name_snapshot,
        url_snapshot=item.url_snapshot,
        snippet_snapshot=item.snippet_snapshot,
    )


def _version_out(version: ReportVersion) -> ReportVersionOut:
    recipients = [str(r) for r in (version.email_recipients or [])]
    return ReportVersionOut(
        id=version.id,
        version_number=version.version_number,
        status_at_version=version.status_at_version,
        content_hash=version.content_hash,
        pdf_storage_key=version.pdf_storage_key,
        pdf_sha256=version.pdf_sha256,
        pdf_bytes=version.pdf_bytes,
        email_status=version.email_status,
        email_recipients=recipients,
        email_error=version.email_error,
        delivered_at=version.delivered_at,
        created_at=version.created_at,
    )


def _report_out(report: Report) -> ReportOut:
    items = sorted(report.items, key=lambda row: row.sort_order)
    versions = sorted(report.versions, key=lambda row: row.version_number)
    return ReportOut(
        id=report.id,
        title=report.title,
        status=report.status,
        period_start=report.period_start,
        period_end=report.period_end,
        notes=report.notes,
        created_at=report.created_at,
        approved_at=report.approved_at,
        archived_at=report.archived_at,
        items=[_item_out(item) for item in items],
        versions=[_version_out(version) for version in versions],
    )


def _branding_out(branding: TenantBranding) -> BrandingOut:
    return BrandingOut(
        display_name=branding.display_name,
        primary_color=branding.primary_color,
        accent_color=branding.accent_color,
        footer_text=branding.footer_text,
        logo_storage_key=branding.logo_storage_key,
    )


@router.post("", response_model=ReportOut, status_code=201)
def create_draft(
    payload: CreateDraftIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> ReportOut:
    report = report_service.create_draft_from_included_matches(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user.id,
        title=payload.title,
        period_start=payload.period_start,
        period_end=payload.period_end,
        notes=payload.notes,
        match_ids=payload.match_ids,
        cutting_ids=payload.cutting_ids,
        include_included_cuttings=payload.include_included_cuttings,
        logo_match_ids=payload.logo_match_ids,
        include_included_logo_matches=payload.include_included_logo_matches,
        social_match_ids=payload.social_match_ids,
        include_included_social_matches=payload.include_included_social_matches,
    )
    return _report_out(report)


@router.get("", response_model=list[ReportOut])
def list_reports(
    status: str | None = Query(default=None),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[ReportOut]:
    rows = report_service.list_reports(db, tenant_id=auth.tenant_id, status=status)
    return [_report_out(r) for r in rows]


@router.get("/branding", response_model=BrandingOut)
def get_branding(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> BrandingOut:
    return _branding_out(report_service.get_or_create_branding(db, auth.tenant_id))


@router.put("/branding", response_model=BrandingOut)
def put_branding(
    payload: BrandingIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> BrandingOut:
    branding = report_service.update_branding(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user.id,
        display_name=payload.display_name,
        primary_color=payload.primary_color,
        accent_color=payload.accent_color,
        footer_text=payload.footer_text,
    )
    return _branding_out(branding)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: UUID,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ReportOut:
    try:
        report = report_service.get_report(db, tenant_id=auth.tenant_id, report_id=report_id)
        return _report_out(report)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc


@router.patch("/{report_id}", response_model=ReportOut)
def patch_report(
    report_id: UUID,
    payload: UpdateReportIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> ReportOut:
    try:
        report = report_service.update_report_meta(
            db,
            tenant_id=auth.tenant_id,
            report_id=report_id,
            actor_id=auth.user.id,
            title=payload.title,
            notes=payload.notes,
            period_start=payload.period_start,
            period_end=payload.period_end,
            status=payload.status,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _report_out(report)


@router.put("/{report_id}/items/reorder", response_model=ReportOut)
def reorder(
    report_id: UUID,
    payload: ReorderIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> ReportOut:
    try:
        report = report_service.reorder_items(
            db,
            tenant_id=auth.tenant_id,
            report_id=report_id,
            actor_id=auth.user.id,
            ordered_item_ids=payload.ordered_item_ids,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _report_out(report)


@router.patch("/{report_id}/items/{item_id}", response_model=ReportOut)
def patch_item(
    report_id: UUID,
    item_id: UUID,
    payload: UpdateItemIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> ReportOut:
    try:
        report = report_service.update_item(
            db,
            tenant_id=auth.tenant_id,
            report_id=report_id,
            item_id=item_id,
            actor_id=auth.user.id,
            note=payload.note,
            included=payload.included,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _report_out(report)


@router.post("/{report_id}/approve", response_model=ReportOut)
def approve(
    report_id: UUID,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> ReportOut:
    try:
        report = report_service.approve_and_render(
            db, tenant_id=auth.tenant_id, report_id=report_id, actor_id=auth.user.id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _report_out(report)


@router.post("/{report_id}/archive", response_model=ReportOut)
def archive(
    report_id: UUID,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> ReportOut:
    try:
        report = report_service.archive_report(
            db, tenant_id=auth.tenant_id, report_id=report_id, actor_id=auth.user.id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    return _report_out(report)


@router.post("/{report_id}/revise", response_model=ReportOut, status_code=201)
def revise(
    report_id: UUID,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> ReportOut:
    try:
        report = report_service.create_revision_draft(
            db, tenant_id=auth.tenant_id, report_id=report_id, actor_id=auth.user.id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _report_out(report)


@router.get("/{report_id}/versions/{version_number}/pdf")
def download_pdf(
    report_id: UUID,
    version_number: int,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> Response:
    try:
        report = report_service.get_report(db, tenant_id=auth.tenant_id, report_id=report_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report not found") from exc
    version = next((v for v in report.versions if v.version_number == version_number), None)
    if version is None or version.pdf_storage_key is None:
        raise HTTPException(status_code=404, detail="PDF not found")
    data = get_storage().get_bytes(version.pdf_storage_key)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="report-v{version_number}.pdf"',
            "X-Content-Hash": version.content_hash,
            "X-PDF-SHA256": version.pdf_sha256 or "",
        },
    )


@router.post("/{report_id}/versions/{version_number}/deliver", response_model=ReportVersionOut)
def deliver(
    report_id: UUID,
    version_number: int,
    payload: DeliverIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> ReportVersionOut:
    try:
        version = report_service.deliver_version(
            db,
            tenant_id=auth.tenant_id,
            report_id=report_id,
            version_number=version_number,
            actor_id=auth.user.id,
            recipients=[str(r) for r in payload.recipients],
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Report version not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _version_out(version)
