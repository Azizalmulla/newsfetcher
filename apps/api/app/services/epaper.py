from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import LegalGate
from app.models.epaper import Cutting, EpaperEdition, EpaperPage, OcrBlock
from app.models.monitoring import MonitoringEntity
from app.models.sources import SourceChannel
from app.services.audit import write_audit
from app.services.matching import entity_terms
from app.services.matching_engine import match_document
from app.services.ocr import resolve_page_ocr
from app.services.pdf_text import extract_text_layer
from app.services.storage import get_storage, sha256_hex


def _channel_epaper_allowed(db: Session, channel_id: UUID) -> tuple[bool, str]:
    channel = db.scalar(
        select(SourceChannel)
        .where(SourceChannel.id == channel_id)
        .options(
            selectinload(SourceChannel.assessment),
            selectinload(SourceChannel.connector_config),
        )
    )
    if channel is None:
        return False, "channel_not_found"
    if channel.assessment is None or channel.assessment.legal_gate != LegalGate.approved:
        return False, "legal_gate_pending"
    if channel.connector_config is None or not channel.connector_config.enabled:
        return False, "connector_disabled"
    ctype = getattr(
        channel.connector_config.connector_type,
        "value",
        channel.connector_config.connector_type,
    )
    if str(ctype) != "epaper":
        return False, "connector_not_epaper"
    return True, "ok"


def ingest_edition_pdf(
    db: Session,
    *,
    channel_id: UUID,
    edition_date: date,
    pdf_bytes: bytes,
    actor_id: UUID | None,
    title: str | None = None,
    source_url: str | None = None,
    require_legal_gate: bool = True,
    ingest_mode: str = "upload",
) -> EpaperEdition:
    """Store PDF, extract text layer, OCR weak pages, persist blocks.

    `require_legal_gate=True` for live/licensed paths. Fixture uploads in tests may
    set False only for controlled offline PDFs (never live publisher fetch).
    """
    channel = db.get(SourceChannel, channel_id)
    if channel is None:
        raise KeyError("Source channel not found")

    if require_legal_gate:
        ok, reason = _channel_epaper_allowed(db, channel_id)
        if not ok:
            raise PermissionError(reason)

    digest = sha256_hex(pdf_bytes)
    existing = db.scalar(
        select(EpaperEdition).where(
            EpaperEdition.source_channel_id == channel_id,
            EpaperEdition.edition_date == edition_date,
        )
    )
    if existing and existing.pdf_sha256 == digest and existing.status == "ocr_done":
        return get_edition(db, existing.id)

    storage_key = f"epaper/{channel_id}/{edition_date.isoformat()}/{digest}.pdf"
    get_storage().put_bytes(storage_key, pdf_bytes, content_type="application/pdf")

    edition = existing or EpaperEdition(
        id=uuid4(),
        publisher_id=channel.publisher_id,
        source_channel_id=channel_id,
        edition_date=edition_date,
    )
    edition.title = title or f"E-paper {edition_date.isoformat()}"
    edition.source_url = source_url
    edition.status = "downloaded"
    edition.pdf_storage_key = storage_key
    edition.pdf_sha256 = digest
    edition.pdf_bytes = len(pdf_bytes)
    edition.ingest_mode = ingest_mode
    edition.failure_reason = None
    if existing is None:
        db.add(edition)
    db.flush()

    # Replace pages/blocks on re-ingest via SQL deletes (avoid ORM nulling FKs).
    old_page_ids = list(
        db.scalars(select(EpaperPage.id).where(EpaperPage.edition_id == edition.id)).all()
    )
    if old_page_ids:
        db.execute(delete(Cutting).where(Cutting.page_id.in_(old_page_ids)))
        db.execute(delete(OcrBlock).where(OcrBlock.page_id.in_(old_page_ids)))
        db.execute(delete(EpaperPage).where(EpaperPage.id.in_(old_page_ids)))
        db.flush()

    extracted = extract_text_layer(pdf_bytes)
    edition.page_count = len(extracted)
    for page_data in extracted:
        page = EpaperPage(
            id=uuid4(),
            edition_id=edition.id,
            page_number=page_data.page_number,
            width=page_data.width,
            height=page_data.height,
            text_layer_chars=len(page_data.text),
            status="processing",
        )
        db.add(page)
        db.flush()
        ocr = resolve_page_ocr(page_data, pdf_bytes=pdf_bytes)
        page.full_text = ocr.text
        page.ocr_provider = ocr.provider
        page.ocr_model = ocr.model
        page.status = "ocr_done"
        page.metadata_ = {"ocr_raw_keys": list(ocr.raw.keys())}
        for block in ocr.blocks:
            db.add(
                OcrBlock(
                    id=uuid4(),
                    page_id=page.id,
                    block_index=block.block_index,
                    text=block.text,
                    source=ocr.provider if ocr.provider != "text_layer" else "text_layer",
                    confidence=block.confidence,
                    bbox_x=block.bbox_x,
                    bbox_y=block.bbox_y,
                    bbox_w=block.bbox_w,
                    bbox_h=block.bbox_h,
                    metadata_={"from": ocr.provider},
                )
            )

    edition.status = "ocr_done"
    write_audit(
        db,
        tenant_id=None,
        actor_id=str(actor_id) if actor_id else None,
        action="epaper.ingested",
        resource_type="epaper_edition",
        resource_id=str(edition.id),
        details={
            "pdf_sha256": digest,
            "page_count": edition.page_count,
            "ingest_mode": ingest_mode,
            "require_legal_gate": require_legal_gate,
        },
    )
    db.commit()
    return get_edition(db, edition.id)


def get_edition(db: Session, edition_id: UUID) -> EpaperEdition:
    edition = db.scalar(
        select(EpaperEdition)
        .where(EpaperEdition.id == edition_id)
        .options(
            selectinload(EpaperEdition.pages).selectinload(EpaperPage.blocks),
            selectinload(EpaperEdition.pages).selectinload(EpaperPage.cuttings),
        )
    )
    if edition is None:
        raise KeyError("Edition not found")
    return edition


def list_editions(db: Session, *, channel_id: UUID | None = None) -> list[EpaperEdition]:
    stmt = (
        select(EpaperEdition)
        .options(selectinload(EpaperEdition.pages))
        .order_by(EpaperEdition.edition_date.desc())
    )
    if channel_id:
        stmt = stmt.where(EpaperEdition.source_channel_id == channel_id)
    return list(db.scalars(stmt).all())


def propose_cuttings_for_tenant(
    db: Session,
    *,
    tenant_id: UUID,
    edition_id: UUID,
) -> dict[str, object]:
    edition = get_edition(db, edition_id)
    entities = db.scalars(
        select(MonitoringEntity)
        .where(
            MonitoringEntity.tenant_id == tenant_id,
            MonitoringEntity.is_active.is_(True),
        )
        .options(
            selectinload(MonitoringEntity.aliases),
            selectinload(MonitoringEntity.exclusions),
        )
    ).all()
    created = 0
    updated = 0
    for entity in entities:
        terms = [term for term in entity_terms(entity) if term.surface]
        exclusions = [row.phrase_normalized for row in entity.exclusions]

        for page in edition.pages:
            text = page.full_text or ""
            if not text.strip():
                continue
            candidate = match_document(
                title=edition.title or "",
                body=text,
                terms=terms,
                exclusions_normalized=exclusions,
            )
            if candidate is None or candidate.excluded:
                continue
            # Anchor bbox to first matching block when possible.
            block = next(
                (
                    b
                    for b in page.blocks
                    if candidate.matched_term.lower() in b.text.lower()
                    or candidate.matched_term in b.text
                ),
                page.blocks[0] if page.blocks else None,
            )
            existing = db.scalar(
                select(Cutting).where(
                    Cutting.tenant_id == tenant_id,
                    Cutting.page_id == page.id,
                    Cutting.entity_id == entity.id,
                )
            )
            if existing is None:
                existing = Cutting(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    page_id=page.id,
                    entity_id=entity.id,
                    status="proposed",
                    matched_term=candidate.matched_term,
                    match_type=candidate.best_match_type,
                    score=candidate.best_score,
                    title=f"{edition.title} — p.{page.page_number}",
                    body_text=candidate.snippet or text[:500],
                    bbox_x=block.bbox_x if block else 0.05,
                    bbox_y=block.bbox_y if block else 0.05,
                    bbox_w=block.bbox_w if block else 0.9,
                    bbox_h=block.bbox_h if block else 0.2,
                    evidence={
                        "hits": [
                            {
                                "match_type": hit.match_type,
                                "score": hit.score,
                                "span": hit.evidence_span,
                            }
                            for hit in candidate.evidence
                        ]
                    },
                )
                db.add(existing)
                created += 1
            else:
                if existing.status in {"proposed", "adjusted"}:
                    existing.matched_term = candidate.matched_term
                    existing.match_type = candidate.best_match_type
                    existing.score = candidate.best_score
                    existing.body_text = candidate.snippet or text[:500]
                    updated += 1
    db.commit()
    return {
        "edition_id": str(edition_id),
        "cuttings_created": created,
        "cuttings_updated": updated,
    }


def set_cutting_decision(
    db: Session,
    *,
    tenant_id: UUID,
    cutting_id: UUID,
    actor_id: UUID,
    status: str,
    note: str | None = None,
    bbox: dict[str, float] | None = None,
    body_text: str | None = None,
) -> Cutting:
    cutting = db.scalar(
        select(Cutting).where(Cutting.id == cutting_id, Cutting.tenant_id == tenant_id)
    )
    if cutting is None:
        raise KeyError("Cutting not found")
    if status not in {"proposed", "included", "excluded", "adjusted"}:
        raise ValueError("Invalid cutting status")
    cutting.status = status
    if note is not None:
        cutting.reviewer_note = note
    if body_text is not None:
        cutting.body_text = body_text
    if bbox:
        cutting.bbox_x = float(bbox.get("x", cutting.bbox_x))
        cutting.bbox_y = float(bbox.get("y", cutting.bbox_y))
        cutting.bbox_w = float(bbox.get("w", cutting.bbox_w))
        cutting.bbox_h = float(bbox.get("h", cutting.bbox_h))
        if status == "proposed":
            cutting.status = "adjusted"
    from datetime import UTC, datetime

    cutting.reviewed_by = actor_id
    cutting.reviewed_at = datetime.now(UTC)
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="cutting.decision",
        resource_type="cutting",
        resource_id=str(cutting.id),
        details={"status": cutting.status},
    )
    db.commit()
    db.refresh(cutting)
    return cutting


def list_cuttings(
    db: Session,
    *,
    tenant_id: UUID,
    edition_id: UUID | None = None,
    status: str | None = None,
) -> list[Cutting]:
    stmt = select(Cutting).where(Cutting.tenant_id == tenant_id).order_by(Cutting.created_at.desc())
    if status:
        stmt = stmt.where(Cutting.status == status)
    if edition_id:
        page_ids = select(EpaperPage.id).where(EpaperPage.edition_id == edition_id)
        stmt = stmt.where(Cutting.page_id.in_(page_ids))
    return list(db.scalars(stmt).all())


def discover_and_ingest_epaper_editions(
    db: Session,
    *,
    channel_id: UUID,
    actor_id: UUID | None = None,
    download: bool = True,
) -> dict[str, object]:
    """Discover public/licensed edition PDFs and optionally ingest them."""
    from datetime import date as date_cls

    from newsfetcher_connectors.politeness import PoliteHttpClient
    from newsfetcher_connectors.registry import get_connector
    from newsfetcher_connectors.types import ConnectorContext, ConnectorType

    from app.models.sources import Publisher

    channel = db.scalar(
        select(SourceChannel)
        .where(SourceChannel.id == channel_id)
        .options(
            selectinload(SourceChannel.assessment),
            selectinload(SourceChannel.connector_config),
            selectinload(SourceChannel.publisher),
        )
    )
    if channel is None:
        return {"ok": False, "reason": "channel_not_found"}
    connector_cfg = channel.connector_config
    if connector_cfg is None:
        return {"ok": False, "reason": "missing_connector_config"}
    ok, reason = _channel_epaper_allowed(db, channel_id)
    if not ok:
        return {"ok": False, "reason": reason}

    publisher: Publisher = channel.publisher
    context = ConnectorContext(
        publisher_code=publisher.code,
        channel_code=channel.code,
        base_url=channel.base_url,
        language=str(getattr(channel.language, "value", channel.language)),
        config=connector_cfg.config or {},
        politeness_delay_ms=connector_cfg.politeness_delay_ms,
        max_requests_per_minute=connector_cfg.max_requests_per_minute,
    )
    result = get_connector(ConnectorType.epaper).discover(context)
    ingested: list[dict[str, object]] = []
    errors = list(result.errors)
    client = PoliteHttpClient(
        user_agent=(
            "NewsFetcherBot/0.1 (+https://newsfetcher.local; media-monitoring; "
            "contact=ops@newsfetcher.local)"
        ),
        politeness_delay_ms=max(connector_cfg.politeness_delay_ms, 800),
        max_requests_per_minute=max(10, connector_cfg.max_requests_per_minute),
        transport_fallback="urllib",
        timeout_seconds=120.0,
    )
    try:
        for item in result.items:
            meta = item.metadata or {}
            if meta.get("kind") != "epaper_edition":
                continue
            pdf_url = str(meta.get("pdf_url") or item.source_url)
            raw_date = meta.get("edition_date") or (item.published_at or "")[:10]
            try:
                edition_date = date_cls.fromisoformat(str(raw_date))
            except ValueError:
                errors.append(f"{pdf_url} -> invalid edition_date")
                continue
            if not download:
                ingested.append(
                    {
                        "edition_date": edition_date.isoformat(),
                        "source_url": pdf_url,
                        "status": "discovered_only",
                    }
                )
                continue
            try:
                response = client.get(pdf_url, use_cache=False)
                if response.status_code >= 400:
                    errors.append(f"{pdf_url} -> HTTP {response.status_code}")
                    continue
                content_type = (response.headers.get("Content-Type") or "").lower()
                if "pdf" not in content_type and not pdf_url.lower().endswith(".pdf"):
                    errors.append(f"{pdf_url} -> not a pdf ({content_type})")
                    continue
                edition = ingest_edition_pdf(
                    db,
                    channel_id=channel_id,
                    edition_date=edition_date,
                    pdf_bytes=response.content,
                    actor_id=actor_id,
                    title=item.title,
                    source_url=pdf_url,
                    require_legal_gate=True,
                    ingest_mode="public_download",
                )
                ingested.append(
                    {
                        "edition_id": str(edition.id),
                        "edition_date": edition_date.isoformat(),
                        "status": edition.status,
                        "page_count": edition.page_count,
                        "source_url": pdf_url,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{pdf_url} -> {exc}")
    finally:
        client.close()

    return {
        "ok": True,
        "discovered": len(result.items),
        "ingested": len(ingested),
        "editions": ingested,
        "errors": errors[:30],
        "error_count": len(errors),
        "connector_meta": result.meta,
    }
