"""Persist deterministic matches into the tenant review inbox."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.arabic import normalize_text
from app.models.articles import Article
from app.models.matching import MatchEvidence, TextMatch
from app.models.monitoring import MonitoringEntity
from app.services.audit import write_audit
from app.services.matching_engine import MatchTerm, match_document


def entity_terms(entity: MonitoringEntity) -> list[MatchTerm]:
    terms: list[MatchTerm] = []
    if entity.canonical_name_en:
        terms.append(
            MatchTerm(
                surface=entity.canonical_name_en,
                normalized=normalize_text(entity.canonical_name_en),
                language="en",
                source="canonical",
            )
        )
    if entity.canonical_name_ar:
        terms.append(
            MatchTerm(
                surface=entity.canonical_name_ar,
                normalized=normalize_text(entity.canonical_name_ar),
                language="ar",
                source="canonical",
            )
        )
    for alias in entity.aliases:
        terms.append(
            MatchTerm(
                surface=alias.alias_text,
                normalized=alias.alias_normalized or normalize_text(alias.alias_text),
                language=alias.language,
                exact_only=alias.exact_only,
                source="alias",
            )
        )
    return terms


def match_article_for_tenant(
    db: Session, *, tenant_id: UUID, article_id: UUID
) -> dict[str, Any]:
    article = db.get(Article, article_id)
    if article is None:
        return {"ok": False, "reason": "article_not_found"}

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
    excluded = 0
    for entity in entities:
        terms = entity_terms(entity)
        if not terms:
            continue
        exclusions = [excl.phrase_normalized for excl in entity.exclusions]
        candidate = match_document(
            title=article.title,
            body=article.body_original,
            terms=terms,
            exclusions_normalized=exclusions,
        )
        if candidate is None:
            continue
        if candidate.excluded:
            excluded += 1
            continue

        existing = db.scalar(
            select(TextMatch).where(
                TextMatch.tenant_id == tenant_id,
                TextMatch.entity_id == entity.id,
                TextMatch.article_id == article.id,
            )
        )
        if existing and existing.status in {"included", "excluded"}:
            # Do not overwrite human decisions.
            continue

        if existing is None:
            existing = TextMatch(
                tenant_id=tenant_id,
                entity_id=entity.id,
                article_id=article.id,
                status="pending_review",
                best_match_type=candidate.best_match_type,
                best_score=candidate.best_score,
                matched_term=candidate.matched_term,
                matched_term_normalized=candidate.matched_term_normalized,
                snippet=candidate.snippet,
            )
            db.add(existing)
            db.flush()
            created += 1
        else:
            existing.best_match_type = candidate.best_match_type
            existing.best_score = candidate.best_score
            existing.matched_term = candidate.matched_term
            existing.matched_term_normalized = candidate.matched_term_normalized
            existing.snippet = candidate.snippet
            existing.status = "pending_review"
            db.execute(delete(MatchEvidence).where(MatchEvidence.text_match_id == existing.id))
            db.flush()
            updated += 1

        for hit in candidate.evidence:
            db.add(
                MatchEvidence(
                    text_match_id=existing.id,
                    tenant_id=tenant_id,
                    match_type=hit.match_type,
                    score=hit.score,
                    surface_form=hit.surface_form,
                    normalized_form=hit.normalized_form,
                    field_name=hit.field_name,
                    start_offset=hit.start_offset,
                    end_offset=hit.end_offset,
                    evidence_span=hit.evidence_span,
                    details=hit.details,
                )
            )

    db.commit()
    return {
        "ok": True,
        "article_id": str(article_id),
        "tenant_id": str(tenant_id),
        "matches_created": created,
        "matches_updated": updated,
        "exclusion_hits": excluded,
    }


def match_all_articles_for_tenant(db: Session, *, tenant_id: UUID) -> dict[str, Any]:
    article_ids = list(db.scalars(select(Article.id)).all())
    totals = {"matches_created": 0, "matches_updated": 0, "exclusion_hits": 0, "articles": 0}
    for article_id in article_ids:
        result = match_article_for_tenant(db, tenant_id=tenant_id, article_id=article_id)
        if result.get("ok"):
            totals["matches_created"] += int(result.get("matches_created", 0))
            totals["matches_updated"] += int(result.get("matches_updated", 0))
            totals["exclusion_hits"] += int(result.get("exclusion_hits", 0))
            totals["articles"] += 1
    return {"ok": True, "tenant_id": str(tenant_id), **totals}


def set_match_decision(
    db: Session,
    *,
    tenant_id: UUID,
    match_id: UUID,
    status: str,
    actor_id: UUID,
    note: str | None = None,
) -> TextMatch:
    if status not in {"included", "excluded", "pending_review"}:
        raise ValueError("invalid status")
    match = db.scalar(
        select(TextMatch).where(TextMatch.id == match_id, TextMatch.tenant_id == tenant_id)
    )
    if match is None:
        raise KeyError("match_not_found")
    match.status = status
    match.reviewer_note = note
    match.reviewed_by = actor_id
    match.reviewed_at = datetime.now(UTC)
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action=f"match.{status}",
        resource_type="text_match",
        resource_id=str(match.id),
        details={"note": note},
    )
    db.commit()
    db.refresh(match)
    return match
