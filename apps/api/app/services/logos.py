from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.articles import ArticleImage
from app.models.epaper import EpaperPage
from app.models.logos import LogoDetection, LogoMatch, TenantLogoTemplate
from app.services.audit import write_audit
from app.services.logo_detection import (
    get_logo_detector,
    image_fingerprint,
    score_template_match,
)
from app.services.storage import get_storage, sha256_hex

ALLOWED_IMAGE_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
MAX_TEMPLATE_BYTES = 2 * 1024 * 1024


def create_logo_template(
    db: Session,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    label: str,
    image_bytes: bytes,
    content_type: str = "image/png",
    entity_id: UUID | None = None,
    variant: str = "primary",
    track_role: str = "own",
    min_confidence: float = 0.72,
) -> TenantLogoTemplate:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(f"Unsupported content type: {content_type}")
    if not image_bytes or len(image_bytes) > MAX_TEMPLATE_BYTES:
        raise ValueError("Logo template must be between 1 byte and 2MB")
    if track_role not in {"own", "competitor", "other"}:
        raise ValueError("track_role must be own|competitor|other")

    digest = sha256_hex(image_bytes)
    existing = db.scalar(
        select(TenantLogoTemplate).where(
            TenantLogoTemplate.tenant_id == tenant_id,
            TenantLogoTemplate.content_hash == digest,
        )
    )
    if existing is not None:
        return existing

    key = f"tenants/{tenant_id}/logo-templates/{digest}"
    get_storage().put_bytes(key, image_bytes, content_type=content_type)
    template = TenantLogoTemplate(
        id=uuid4(),
        tenant_id=tenant_id,
        entity_id=entity_id,
        label=label,
        variant=variant,
        track_role=track_role,
        storage_key=key,
        content_hash=digest,
        byte_size=len(image_bytes),
        content_type=content_type,
        min_confidence=min_confidence,
        feature_fingerprint=image_fingerprint(image_bytes),
        metadata_={"phase": 9},
    )
    db.add(template)
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="logo.template_created",
        resource_type="logo_template",
        resource_id=str(template.id),
        details={"label": label, "track_role": track_role},
    )
    db.commit()
    db.refresh(template)
    return template


def list_templates(
    db: Session, *, tenant_id: UUID, active_only: bool = True
) -> list[TenantLogoTemplate]:
    stmt = select(TenantLogoTemplate).where(TenantLogoTemplate.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(TenantLogoTemplate.is_active.is_(True))
    return list(db.scalars(stmt.order_by(TenantLogoTemplate.created_at.desc())).all())


def _load_scan_bytes(
    db: Session,
    *,
    page_id: UUID | None,
    article_image_id: UUID | None,
) -> tuple[bytes, str]:
    if bool(page_id) == bool(article_image_id):
        raise ValueError("Provide exactly one of page_id or article_image_id")
    storage = get_storage()
    if page_id:
        page = db.scalar(
            select(EpaperPage)
            .where(EpaperPage.id == page_id)
            .options(selectinload(EpaperPage.edition))
        )
        if page is None:
            raise KeyError("E-paper page not found")
        if page.render_storage_key and storage.exists(page.render_storage_key):
            return storage.get_bytes(page.render_storage_key), "page_render"
        edition = page.edition
        if edition and edition.pdf_storage_key and storage.exists(edition.pdf_storage_key):
            # Local cascade can screen PDF bytes; not a visual crop substitute.
            return storage.get_bytes(edition.pdf_storage_key), "edition_pdf"
        raise ValueError("No stored image/PDF bytes available for page")
    image = db.get(ArticleImage, article_image_id)
    if image is None:
        raise KeyError("Article image not found")
    if image.storage_key and storage.exists(image.storage_key):
        return storage.get_bytes(image.storage_key), "article_image"
    # Fixture path: fingerprint the source URL when binary not stored yet.
    return image.source_url.encode("utf-8"), "article_image_url_stub"


def run_detect_and_propose(
    db: Session,
    *,
    tenant_id: UUID,
    actor_id: UUID,
    page_id: UUID | None = None,
    article_image_id: UUID | None = None,
) -> dict[str, object]:
    templates = list_templates(db, tenant_id=tenant_id, active_only=True)
    if not templates:
        raise ValueError("No active logo templates for tenant")

    image_bytes, source_kind = _load_scan_bytes(
        db, page_id=page_id, article_image_id=article_image_id
    )
    fingerprints = [
        (str(t.id), t.feature_fingerprint or t.content_hash, t.min_confidence)
        for t in templates
        if t.feature_fingerprint or t.content_hash
    ]
    detector = get_logo_detector()
    result = detector.detect(image_bytes=image_bytes, template_fingerprints=fingerprints)

    template_by_id = {str(t.id): t for t in templates}
    detections_created = 0
    matches_created = 0
    matches_updated = 0

    for cand in result.candidates:
        template_id = str(cand.evidence.get("template_id") or "")
        template = template_by_id.get(template_id)
        if template is None:
            continue
        detection = LogoDetection(
            id=uuid4(),
            tenant_id=tenant_id,
            page_id=page_id,
            article_image_id=article_image_id,
            provider=result.provider,
            model=result.model,
            stage=cand.stage,
            confidence=cand.confidence,
            bbox_x=cand.bbox_x,
            bbox_y=cand.bbox_y,
            bbox_w=cand.bbox_w,
            bbox_h=cand.bbox_h,
            evidence={**cand.evidence, "source_kind": source_kind},
            raw=cand.raw,
        )
        db.add(detection)
        db.flush()
        detections_created += 1

        similarity = float(cand.evidence.get("similarity") or 0.0)
        score = score_template_match(
            candidate_confidence=cand.confidence,
            similarity=similarity,
            min_confidence=template.min_confidence,
        )
        existing = db.scalar(
            select(LogoMatch).where(
                LogoMatch.tenant_id == tenant_id,
                LogoMatch.template_id == template.id,
                LogoMatch.detection_id == detection.id,
            )
        )
        if existing is None:
            db.add(
                LogoMatch(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    template_id=template.id,
                    detection_id=detection.id,
                    entity_id=template.entity_id,
                    status="proposed",  # never auto-include
                    score=score,
                    match_stage=cand.stage,
                    evidence={
                        "cascade": cand.evidence.get("cascade"),
                        "similarity": similarity,
                        "detection_confidence": cand.confidence,
                        "auto_finalized": False,
                    },
                )
            )
            matches_created += 1
        else:
            if existing.status == "proposed":
                existing.score = score
                existing.match_stage = cand.stage
                matches_updated += 1

    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="logo.detect_proposed",
        resource_type="logo_detection",
        resource_id=str(page_id or article_image_id),
        details={
            "provider": result.provider,
            "model": result.model,
            "detections_created": detections_created,
            "matches_created": matches_created,
            "screened_out": result.screened_out,
            "auto_finalized": False,
        },
    )
    db.commit()
    return {
        "provider": result.provider,
        "model": result.model,
        "source_kind": source_kind,
        "detections_created": detections_created,
        "matches_created": matches_created,
        "matches_updated": matches_updated,
        "screened_out": result.screened_out,
        "auto_finalized": False,
    }


def list_matches(
    db: Session,
    *,
    tenant_id: UUID,
    status: str | None = None,
) -> list[LogoMatch]:
    stmt = (
        select(LogoMatch)
        .where(LogoMatch.tenant_id == tenant_id)
        .options(selectinload(LogoMatch.detection), selectinload(LogoMatch.template))
        .order_by(LogoMatch.created_at.desc())
    )
    if status:
        stmt = stmt.where(LogoMatch.status == status)
    return list(db.scalars(stmt).all())


def set_match_decision(
    db: Session,
    *,
    tenant_id: UUID,
    match_id: UUID,
    actor_id: UUID,
    status: str,
    note: str | None = None,
    bbox: dict[str, float] | None = None,
) -> LogoMatch:
    match = db.scalar(
        select(LogoMatch)
        .where(LogoMatch.id == match_id, LogoMatch.tenant_id == tenant_id)
        .options(selectinload(LogoMatch.detection))
    )
    if match is None:
        raise KeyError("Logo match not found")
    if status not in {"proposed", "included", "excluded", "adjusted"}:
        raise ValueError("Invalid logo match status")
    match.status = status
    if note is not None:
        match.reviewer_note = note
    if bbox and match.detection is not None:
        match.detection.bbox_x = float(bbox.get("x", match.detection.bbox_x))
        match.detection.bbox_y = float(bbox.get("y", match.detection.bbox_y))
        match.detection.bbox_w = float(bbox.get("w", match.detection.bbox_w))
        match.detection.bbox_h = float(bbox.get("h", match.detection.bbox_h))
        if status == "proposed":
            match.status = "adjusted"
    match.reviewed_by = actor_id
    match.reviewed_at = datetime.now(UTC)
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="logo.match_decision",
        resource_type="logo_match",
        resource_id=str(match.id),
        details={"status": match.status},
    )
    db.commit()
    db.refresh(match)
    return match
