from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import AuthContext, get_current_auth, require_roles
from app.db.session import get_db
from app.models.articles import Article
from app.models.monitoring import MonitoringEntity
from app.models.semantic import SemanticCandidate, TenantMatchThreshold
from app.services.audit import write_audit
from app.services.semantic_matching import run_semantic_matching_for_tenant

router = APIRouter(prefix="/semantic", tags=["semantic"])


class SemanticCandidateOut(BaseModel):
    id: UUID
    entity_id: UUID
    entity_name_en: str | None
    article_id: UUID
    article_title: str | None
    vector_similarity: float
    rerank_score: float | None
    lexical_best_score: float
    classifier_score: float
    classifier_label: str
    status: str
    provenance: dict[str, Any]
    created_at: datetime


class ThresholdIn(BaseModel):
    min_cosine: float = Field(ge=0.0, le=1.0)
    min_rerank: float = Field(ge=0.0, le=1.0)
    min_classifier: float = Field(ge=0.0, le=1.0, default=0.6)


class ThresholdOut(BaseModel):
    tenant_id: UUID
    min_cosine: float
    min_rerank: float
    min_classifier: float


class DecisionIn(BaseModel):
    status: str = Field(pattern=r"^(included|excluded|pending_review)$")


@router.post("/run")
def run_semantic(
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer", "platform_admin")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return run_semantic_matching_for_tenant(db, tenant_id=auth.tenant_id)


@router.get("/candidates", response_model=list[SemanticCandidateOut])
def list_candidates(
    status: str | None = Query(default="pending_review"),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[SemanticCandidateOut]:
    stmt = (
        select(SemanticCandidate)
        .where(SemanticCandidate.tenant_id == auth.tenant_id)
        .order_by(SemanticCandidate.created_at.desc())
    )
    if status:
        stmt = stmt.where(SemanticCandidate.status == status)
    rows = db.scalars(stmt).all()
    entity_ids = {row.entity_id for row in rows}
    article_ids = {row.article_id for row in rows}
    entities = {}
    articles = {}
    if entity_ids:
        entities = {
            e.id: e
            for e in db.scalars(select(MonitoringEntity).where(MonitoringEntity.id.in_(entity_ids)))
        }
    if article_ids:
        articles = {
            a.id: a for a in db.scalars(select(Article).where(Article.id.in_(article_ids)))
        }
    return [
        SemanticCandidateOut(
            id=row.id,
            entity_id=row.entity_id,
            entity_name_en=(
                entities[row.entity_id].canonical_name_en if row.entity_id in entities else None
            ),
            article_id=row.article_id,
            article_title=(articles[row.article_id].title if row.article_id in articles else None),
            vector_similarity=row.vector_similarity,
            rerank_score=row.rerank_score,
            lexical_best_score=row.lexical_best_score,
            classifier_score=row.classifier_score,
            classifier_label=row.classifier_label,
            status=row.status,
            provenance=row.provenance,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/candidates/{candidate_id}/decision", response_model=SemanticCandidateOut)
def decide_candidate(
    candidate_id: UUID,
    payload: DecisionIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> SemanticCandidateOut:
    row = db.scalar(
        select(SemanticCandidate).where(
            SemanticCandidate.id == candidate_id,
            SemanticCandidate.tenant_id == auth.tenant_id,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    row.status = payload.status
    write_audit(
        db,
        tenant_id=auth.tenant_id,
        actor_id=str(auth.user.id),
        action=f"semantic.{payload.status}",
        resource_type="semantic_candidate",
        resource_id=str(row.id),
    )
    db.commit()
    db.refresh(row)
    entity = db.get(MonitoringEntity, row.entity_id)
    article = db.get(Article, row.article_id)
    return SemanticCandidateOut(
        id=row.id,
        entity_id=row.entity_id,
        entity_name_en=entity.canonical_name_en if entity else None,
        article_id=row.article_id,
        article_title=article.title if article else None,
        vector_similarity=row.vector_similarity,
        rerank_score=row.rerank_score,
        lexical_best_score=row.lexical_best_score,
        classifier_score=row.classifier_score,
        classifier_label=row.classifier_label,
        status=row.status,
        provenance=row.provenance,
        created_at=row.created_at,
    )


@router.get("/thresholds", response_model=ThresholdOut)
def get_thresholds(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> ThresholdOut:
    settings = get_settings()
    row = db.scalar(
        select(TenantMatchThreshold).where(TenantMatchThreshold.tenant_id == auth.tenant_id)
    )
    if row is None:
        return ThresholdOut(
            tenant_id=auth.tenant_id,
            min_cosine=settings.semantic_min_cosine,
            min_rerank=settings.semantic_min_rerank,
            min_classifier=0.6,
        )
    return ThresholdOut(
        tenant_id=auth.tenant_id,
        min_cosine=row.min_cosine,
        min_rerank=row.min_rerank,
        min_classifier=row.min_classifier,
    )


@router.put("/thresholds", response_model=ThresholdOut)
def put_thresholds(
    payload: ThresholdIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "platform_admin")),
    db: Session = Depends(get_db),
) -> ThresholdOut:
    row = db.scalar(
        select(TenantMatchThreshold).where(TenantMatchThreshold.tenant_id == auth.tenant_id)
    )
    if row is None:
        row = TenantMatchThreshold(
            tenant_id=auth.tenant_id,
            min_cosine=payload.min_cosine,
            min_rerank=payload.min_rerank,
            min_classifier=payload.min_classifier,
        )
        db.add(row)
    else:
        row.min_cosine = payload.min_cosine
        row.min_rerank = payload.min_rerank
        row.min_classifier = payload.min_classifier
    write_audit(
        db,
        tenant_id=auth.tenant_id,
        actor_id=str(auth.user.id),
        action="semantic.thresholds_updated",
        resource_type="tenant_match_thresholds",
        resource_id=str(auth.tenant_id),
        details=payload.model_dump(),
    )
    db.commit()
    return ThresholdOut(
        tenant_id=auth.tenant_id,
        min_cosine=payload.min_cosine,
        min_rerank=payload.min_rerank,
        min_classifier=payload.min_classifier,
    )
