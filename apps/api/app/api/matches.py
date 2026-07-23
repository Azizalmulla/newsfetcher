from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import AuthContext, get_current_auth, require_roles
from app.db.session import get_db
from app.models.articles import Article
from app.models.matching import TextMatch
from app.models.monitoring import MonitoringEntity
from app.services.matching import match_all_articles_for_tenant, set_match_decision

router = APIRouter(prefix="/matches", tags=["matches"])


class EvidenceOut(BaseModel):
    match_type: str
    score: float
    surface_form: str
    normalized_form: str
    field_name: str
    start_offset: int | None
    end_offset: int | None
    evidence_span: str


class MatchOut(BaseModel):
    id: UUID
    entity_id: UUID
    entity_name_en: str | None
    entity_name_ar: str | None
    article_id: UUID
    article_title: str | None
    article_url: str | None
    status: str
    best_match_type: str
    best_score: float
    matched_term: str
    snippet: str | None
    reviewer_note: str | None
    reviewed_at: datetime | None
    evidence: list[EvidenceOut]


class DecisionIn(BaseModel):
    status: str = Field(pattern=r"^(included|excluded|pending_review)$")
    note: str | None = None


def _to_out(match: TextMatch, entity: MonitoringEntity | None, article: Article | None) -> MatchOut:
    return MatchOut(
        id=match.id,
        entity_id=match.entity_id,
        entity_name_en=entity.canonical_name_en if entity else None,
        entity_name_ar=entity.canonical_name_ar if entity else None,
        article_id=match.article_id,
        article_title=article.title if article else None,
        article_url=article.canonical_url if article else None,
        status=match.status,
        best_match_type=match.best_match_type,
        best_score=match.best_score,
        matched_term=match.matched_term,
        snippet=match.snippet,
        reviewer_note=match.reviewer_note,
        reviewed_at=match.reviewed_at,
        evidence=[
            EvidenceOut(
                match_type=item.match_type,
                score=item.score,
                surface_form=item.surface_form,
                normalized_form=item.normalized_form,
                field_name=item.field_name,
                start_offset=item.start_offset,
                end_offset=item.end_offset,
                evidence_span=item.evidence_span,
            )
            for item in match.evidence
        ],
    )


@router.get("/inbox", response_model=list[MatchOut])
def list_inbox(
    status: str | None = Query(default="pending_review"),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[MatchOut]:
    stmt = (
        select(TextMatch)
        .where(TextMatch.tenant_id == auth.tenant_id)
        .options(selectinload(TextMatch.evidence))
        .order_by(TextMatch.created_at.desc())
    )
    if status:
        stmt = stmt.where(TextMatch.status == status)
    matches = db.scalars(stmt).all()

    entity_ids = {match.entity_id for match in matches}
    article_ids = {match.article_id for match in matches}
    entities = {}
    articles = {}
    if entity_ids:
        entities = {
            entity.id: entity
            for entity in db.scalars(
                select(MonitoringEntity).where(MonitoringEntity.id.in_(entity_ids))
            ).all()
        }
    if article_ids:
        articles = {
            article.id: article
            for article in db.scalars(select(Article).where(Article.id.in_(article_ids))).all()
        }
    return [
        _to_out(match, entities.get(match.entity_id), articles.get(match.article_id))
        for match in matches
    ]


@router.post("/{match_id}/decision", response_model=MatchOut)
def decide_match(
    match_id: UUID,
    payload: DecisionIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> MatchOut:
    try:
        match = set_match_decision(
            db,
            tenant_id=auth.tenant_id,
            match_id=match_id,
            status=payload.status,
            actor_id=auth.user.id,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Match not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    loaded = db.scalar(
        select(TextMatch)
        .where(TextMatch.id == match.id)
        .options(selectinload(TextMatch.evidence))
    )
    assert loaded is not None
    entity = db.get(MonitoringEntity, loaded.entity_id)
    article = db.get(Article, loaded.article_id)
    return _to_out(loaded, entity, article)


@router.post("/run")
def run_matching(
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer", "platform_admin")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Run deterministic matching for the current tenant across known articles."""
    return match_all_articles_for_tenant(db, tenant_id=auth.tenant_id)
