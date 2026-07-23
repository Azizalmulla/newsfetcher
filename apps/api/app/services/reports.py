from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.articles import Article
from app.models.epaper import Cutting
from app.models.logos import LogoMatch
from app.models.matching import TextMatch
from app.models.reports import Report, ReportItem, ReportVersion, TenantBranding
from app.models.social import SocialMatch
from app.models.sources import Publisher
from app.models.tenancy import Tenant
from app.services.audit import write_audit
from app.services.email_delivery import deliver_report_email
from app.services.pdf_report import render_press_clipping_pdf
from app.services.storage import get_storage, sha256_hex

EDITABLE_STATUSES = frozenset({"draft", "in_review"})


def _ensure_editable(report: Report) -> None:
    if report.status not in EDITABLE_STATUSES:
        raise ValueError(f"Report status '{report.status}' is immutable; create a revision draft")


def get_or_create_branding(db: Session, tenant_id: UUID) -> TenantBranding:
    branding = db.get(TenantBranding, tenant_id)
    if branding is None:
        tenant = db.get(Tenant, tenant_id)
        branding = TenantBranding(
            tenant_id=tenant_id,
            display_name=tenant.name if tenant else None,
            footer_text="Confidential press clipping — NewsFetcher",
        )
        db.add(branding)
        db.flush()
    return branding


def create_draft_from_included_matches(
    db: Session,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    title: str,
    period_start: date | None = None,
    period_end: date | None = None,
    notes: str | None = None,
    match_ids: list[UUID] | None = None,
    cutting_ids: list[UUID] | None = None,
    include_included_cuttings: bool = True,
    logo_match_ids: list[UUID] | None = None,
    include_included_logo_matches: bool = True,
    social_match_ids: list[UUID] | None = None,
    include_included_social_matches: bool = True,
) -> Report:
    report = Report(
        id=uuid4(),
        tenant_id=tenant_id,
        title=title,
        status="draft",
        period_start=period_start,
        period_end=period_end,
        notes=notes,
        created_by=actor_id,
    )
    db.add(report)
    db.flush()

    stmt = (
        select(TextMatch)
        .where(TextMatch.tenant_id == tenant_id, TextMatch.status == "included")
        .order_by(TextMatch.reviewed_at.desc().nullslast(), TextMatch.created_at.desc())
    )
    if match_ids:
        stmt = stmt.where(TextMatch.id.in_(match_ids))
    matches = db.scalars(stmt).all()

    article_ids = {m.article_id for m in matches}
    articles = {
        a.id: a for a in db.scalars(select(Article).where(Article.id.in_(article_ids))).all()
    } if article_ids else {}
    publisher_ids = {a.publisher_id for a in articles.values()}
    publishers = {
        p.id: p for p in db.scalars(select(Publisher).where(Publisher.id.in_(publisher_ids))).all()
    } if publisher_ids else {}

    sort_order = 0
    for match in matches:
        article = articles.get(match.article_id)
        publisher = publishers.get(article.publisher_id) if article else None
        db.add(
            ReportItem(
                id=uuid4(),
                report_id=report.id,
                tenant_id=tenant_id,
                text_match_id=match.id,
                article_id=match.article_id,
                entity_id=match.entity_id,
                sort_order=sort_order,
                included=True,
                title_snapshot=article.title if article else match.matched_term,
                source_name_snapshot=publisher.name_en if publisher else None,
                url_snapshot=article.canonical_url if article else None,
                snippet_snapshot=match.snippet,
            )
        )
        sort_order += 1

    cuttings: list[Cutting] = []
    if cutting_ids or include_included_cuttings:
        cutting_stmt = select(Cutting).where(Cutting.tenant_id == tenant_id)
        if cutting_ids:
            cutting_stmt = cutting_stmt.where(Cutting.id.in_(cutting_ids))
        else:
            cutting_stmt = cutting_stmt.where(Cutting.status == "included")
        cuttings = list(db.scalars(cutting_stmt.order_by(Cutting.created_at.desc())).all())
    for cutting in cuttings:
        db.add(
            ReportItem(
                id=uuid4(),
                report_id=report.id,
                tenant_id=tenant_id,
                cutting_id=cutting.id,
                entity_id=cutting.entity_id,
                sort_order=sort_order,
                included=True,
                title_snapshot=cutting.title or cutting.matched_term,
                source_name_snapshot="E-paper",
                url_snapshot=None,
                snippet_snapshot=cutting.body_text[:500],
            )
        )
        sort_order += 1

    logo_matches: list[LogoMatch] = []
    if logo_match_ids or include_included_logo_matches:
        logo_stmt = select(LogoMatch).where(LogoMatch.tenant_id == tenant_id)
        if logo_match_ids:
            logo_stmt = logo_stmt.where(LogoMatch.id.in_(logo_match_ids))
        else:
            logo_stmt = logo_stmt.where(LogoMatch.status == "included")
        logo_matches = list(db.scalars(logo_stmt.order_by(LogoMatch.created_at.desc())).all())
    for logo_match in logo_matches:
        db.add(
            ReportItem(
                id=uuid4(),
                report_id=report.id,
                tenant_id=tenant_id,
                logo_match_id=logo_match.id,
                entity_id=logo_match.entity_id,
                sort_order=sort_order,
                included=True,
                title_snapshot=f"Logo match ({logo_match.match_stage})",
                source_name_snapshot="Logo recognition",
                url_snapshot=None,
                snippet_snapshot=f"score={logo_match.score:.3f} status={logo_match.status}",
            )
        )
        sort_order += 1

    social_matches: list[SocialMatch] = []
    if social_match_ids or include_included_social_matches:
        social_stmt = select(SocialMatch).where(SocialMatch.tenant_id == tenant_id)
        if social_match_ids:
            social_stmt = social_stmt.where(SocialMatch.id.in_(social_match_ids))
        else:
            social_stmt = social_stmt.where(SocialMatch.status == "included")
        social_matches = list(
            db.scalars(social_stmt.order_by(SocialMatch.created_at.desc())).all()
        )
    for social_match in social_matches:
        db.add(
            ReportItem(
                id=uuid4(),
                report_id=report.id,
                tenant_id=tenant_id,
                social_match_id=social_match.id,
                entity_id=social_match.entity_id,
                sort_order=sort_order,
                included=True,
                title_snapshot=f"Social: {social_match.matched_term}",
                source_name_snapshot="X / social",
                url_snapshot=None,
                snippet_snapshot=social_match.snippet,
            )
        )
        sort_order += 1

    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="report.draft_created",
        resource_type="report",
        resource_id=str(report.id),
        details={
            "match_count": len(matches),
            "cutting_count": len(cuttings),
            "logo_match_count": len(logo_matches),
            "social_match_count": len(social_matches),
            "title": title,
        },
    )
    db.commit()
    return get_report(db, tenant_id=tenant_id, report_id=report.id)


def get_report(db: Session, *, tenant_id: UUID, report_id: UUID) -> Report:
    report = db.scalar(
        select(Report)
        .where(Report.id == report_id, Report.tenant_id == tenant_id)
        .options(selectinload(Report.items), selectinload(Report.versions))
    )
    if report is None:
        raise KeyError("Report not found")
    return report


def list_reports(db: Session, *, tenant_id: UUID, status: str | None = None) -> list[Report]:
    stmt = (
        select(Report)
        .where(Report.tenant_id == tenant_id)
        .options(selectinload(Report.items), selectinload(Report.versions))
        .order_by(Report.created_at.desc())
    )
    if status:
        stmt = stmt.where(Report.status == status)
    return list(db.scalars(stmt).all())


def update_report_meta(
    db: Session,
    *,
    tenant_id: UUID,
    report_id: UUID,
    actor_id: UUID,
    title: str | None = None,
    notes: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
    status: str | None = None,
) -> Report:
    report = get_report(db, tenant_id=tenant_id, report_id=report_id)
    _ensure_editable(report)
    if title is not None:
        report.title = title
    if notes is not None:
        report.notes = notes
    if period_start is not None:
        report.period_start = period_start
    if period_end is not None:
        report.period_end = period_end
    if status is not None:
        if status not in {"draft", "in_review"}:
            raise ValueError("Use approve/archive endpoints for final states")
        report.status = status
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="report.updated",
        resource_type="report",
        resource_id=str(report.id),
    )
    db.commit()
    return get_report(db, tenant_id=tenant_id, report_id=report_id)


def reorder_items(
    db: Session,
    *,
    tenant_id: UUID,
    report_id: UUID,
    actor_id: UUID,
    ordered_item_ids: list[UUID],
) -> Report:
    report = get_report(db, tenant_id=tenant_id, report_id=report_id)
    _ensure_editable(report)
    items = {item.id: item for item in report.items}
    if set(ordered_item_ids) != set(items):
        raise ValueError("ordered_item_ids must include every report item exactly once")

    # Two-phase update avoids unique (report_id, sort_order) collisions.
    for offset, item_id in enumerate(ordered_item_ids):
        items[item_id].sort_order = 10_000 + offset
    db.flush()
    for sort_order, item_id in enumerate(ordered_item_ids):
        items[item_id].sort_order = sort_order

    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="report.reordered",
        resource_type="report",
        resource_id=str(report.id),
    )
    db.commit()
    return get_report(db, tenant_id=tenant_id, report_id=report_id)


def update_item(
    db: Session,
    *,
    tenant_id: UUID,
    report_id: UUID,
    item_id: UUID,
    actor_id: UUID,
    note: str | None = None,
    included: bool | None = None,
) -> Report:
    report = get_report(db, tenant_id=tenant_id, report_id=report_id)
    _ensure_editable(report)
    item = next((row for row in report.items if row.id == item_id), None)
    if item is None:
        raise KeyError("Report item not found")
    if note is not None:
        item.note = note
    if included is not None:
        item.included = included
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="report.item_updated",
        resource_type="report_item",
        resource_id=str(item_id),
    )
    db.commit()
    return get_report(db, tenant_id=tenant_id, report_id=report_id)


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def build_snapshot(db: Session, report: Report, *, version_number: int) -> dict[str, Any]:
    branding = get_or_create_branding(db, report.tenant_id)
    tenant = db.get(Tenant, report.tenant_id)
    items = sorted(report.items, key=lambda item: item.sort_order)
    payload: dict[str, Any] = {
        "report_id": str(report.id),
        "tenant_id": str(report.tenant_id),
        "tenant_name": tenant.name if tenant else None,
        "title": report.title,
        "notes": report.notes,
        "period_start": report.period_start.isoformat() if report.period_start else None,
        "period_end": report.period_end.isoformat() if report.period_end else None,
        "version_number": version_number,
        "branding": {
            "display_name": branding.display_name,
            "primary_color": branding.primary_color,
            "accent_color": branding.accent_color,
            "footer_text": branding.footer_text,
            "logo_storage_key": branding.logo_storage_key,
        },
        "items": [
            {
                "id": str(item.id),
                "sort_order": item.sort_order,
                "included": item.included,
                "note": item.note,
                "text_match_id": str(item.text_match_id) if item.text_match_id else None,
                "article_id": str(item.article_id) if item.article_id else None,
                "entity_id": str(item.entity_id) if item.entity_id else None,
                "title_snapshot": item.title_snapshot,
                "source_name_snapshot": item.source_name_snapshot,
                "url_snapshot": item.url_snapshot,
                "snippet_snapshot": item.snippet_snapshot,
            }
            for item in items
        ],
    }
    digest = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    payload["content_hash"] = digest
    return payload


def approve_and_render(
    db: Session,
    *,
    tenant_id: UUID,
    report_id: UUID,
    actor_id: UUID,
) -> Report:
    report = get_report(db, tenant_id=tenant_id, report_id=report_id)
    _ensure_editable(report)
    if not any(item.included for item in report.items):
        raise ValueError("Cannot approve a report with zero included items")

    next_version = (
        db.scalar(
            select(func.coalesce(func.max(ReportVersion.version_number), 0)).where(
                ReportVersion.report_id == report.id
            )
        )
        or 0
    ) + 1
    snapshot = build_snapshot(db, report, version_number=next_version)
    pdf_bytes = render_press_clipping_pdf(snapshot)
    pdf_hash = sha256_hex(pdf_bytes)
    storage_key = f"tenants/{tenant_id}/reports/{report.id}/v{next_version}.pdf"
    storage = get_storage()
    storage.put_bytes(storage_key, pdf_bytes, content_type="application/pdf")

    version = ReportVersion(
        id=uuid4(),
        report_id=report.id,
        tenant_id=tenant_id,
        version_number=next_version,
        status_at_version="final",
        snapshot=snapshot,
        content_hash=snapshot["content_hash"],
        pdf_storage_key=storage_key,
        pdf_sha256=pdf_hash,
        pdf_bytes=len(pdf_bytes),
        created_by=actor_id,
        email_status="pending",
        email_recipients=[],
    )
    db.add(version)
    report.status = "final"
    report.approved_by = actor_id
    report.approved_at = datetime.now(UTC)
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="report.approved",
        resource_type="report",
        resource_id=str(report.id),
        details={
            "version": next_version,
            "content_hash": snapshot["content_hash"],
            "pdf_sha256": pdf_hash,
        },
    )
    db.commit()
    return get_report(db, tenant_id=tenant_id, report_id=report_id)


def archive_report(
    db: Session,
    *,
    tenant_id: UUID,
    report_id: UUID,
    actor_id: UUID,
) -> Report:
    report = get_report(db, tenant_id=tenant_id, report_id=report_id)
    if report.status == "archived":
        return report
    report.status = "archived"
    report.archived_at = datetime.now(UTC)
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="report.archived",
        resource_type="report",
        resource_id=str(report.id),
    )
    db.commit()
    return get_report(db, tenant_id=tenant_id, report_id=report_id)


def create_revision_draft(
    db: Session,
    *,
    tenant_id: UUID,
    report_id: UUID,
    actor_id: UUID,
) -> Report:
    source = get_report(db, tenant_id=tenant_id, report_id=report_id)
    if source.status not in {"final", "archived"}:
        raise ValueError("Revision drafts can only be created from final/archived reports")
    draft = Report(
        id=uuid4(),
        tenant_id=tenant_id,
        title=f"{source.title} (revision)",
        status="draft",
        period_start=source.period_start,
        period_end=source.period_end,
        notes=source.notes,
        created_by=actor_id,
    )
    db.add(draft)
    db.flush()
    for item in sorted(source.items, key=lambda row: row.sort_order):
        db.add(
            ReportItem(
                id=uuid4(),
                report_id=draft.id,
                tenant_id=tenant_id,
                text_match_id=item.text_match_id,
                article_id=item.article_id,
                entity_id=item.entity_id,
                sort_order=item.sort_order,
                included=item.included,
                note=item.note,
                title_snapshot=item.title_snapshot,
                source_name_snapshot=item.source_name_snapshot,
                url_snapshot=item.url_snapshot,
                snippet_snapshot=item.snippet_snapshot,
            )
        )
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="report.revision_created",
        resource_type="report",
        resource_id=str(draft.id),
        details={"source_report_id": str(source.id)},
    )
    db.commit()
    return get_report(db, tenant_id=tenant_id, report_id=draft.id)


def deliver_version(
    db: Session,
    *,
    tenant_id: UUID,
    report_id: UUID,
    version_number: int,
    actor_id: UUID,
    recipients: list[str],
) -> ReportVersion:
    report = get_report(db, tenant_id=tenant_id, report_id=report_id)
    version = next((v for v in report.versions if v.version_number == version_number), None)
    if version is None or version.pdf_storage_key is None:
        raise KeyError("Report version not found")
    pdf_bytes = get_storage().get_bytes(version.pdf_storage_key)
    try:
        result = deliver_report_email(
            recipients=recipients,
            subject=f"{report.title} — v{version.version_number}",
            body=(
                f"Attached is the approved press-clipping report.\n"
                f"Version: {version.version_number}\n"
                f"Content hash: {version.content_hash}\n"
            ),
            pdf_bytes=pdf_bytes,
            pdf_filename=f"report-{report.id}-v{version.version_number}.pdf",
        )
        version.email_status = "sent"
        version.email_error = None
        version.delivered_at = datetime.now(UTC)
        version.email_recipients = recipients
        write_audit(
            db,
            tenant_id=tenant_id,
            actor_id=str(actor_id),
            action="report.delivered",
            resource_type="report_version",
            resource_id=str(version.id),
            details=result,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001
        version.email_status = "failed"
        version.email_error = str(exc)
        version.email_recipients = recipients
        db.commit()
        raise
    return version


def update_branding(
    db: Session,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    display_name: str | None = None,
    primary_color: str | None = None,
    accent_color: str | None = None,
    footer_text: str | None = None,
) -> TenantBranding:
    branding = get_or_create_branding(db, tenant_id)
    if display_name is not None:
        branding.display_name = display_name
    if primary_color is not None:
        branding.primary_color = primary_color
    if accent_color is not None:
        branding.accent_color = accent_color
    if footer_text is not None:
        branding.footer_text = footer_text
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="branding.updated",
        resource_type="tenant_branding",
        resource_id=str(tenant_id),
    )
    db.commit()
    return get_or_create_branding(db, tenant_id)
