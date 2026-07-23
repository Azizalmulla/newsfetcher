"""Semantic retrieval pipeline (Phase 5).

Flow:
entity instruction/names → embed → retrieve top-K → rerank →
aggregate lexical evidence → relevance classifier → review candidates.

Semantic scores never independently confirm a final match.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.arabic import normalize_text
from app.core.config import get_settings
from app.models.articles import Article
from app.models.matching import TextMatch
from app.models.monitoring import MonitoringEntity
from app.models.semantic import (
    ArticleEmbedding,
    EntityEmbedding,
    RelevanceDecision,
    SemanticCandidate,
    TenantMatchThreshold,
)
from app.services.embeddings import cosine_similarity, get_embedding_provider
from app.services.llm import get_llm_client
from app.services.matching_engine import MatchTerm, match_document
from app.services.relevance import RelevanceResult, classify_relevance
from app.services.rerank import get_rerank_provider


def _entity_query_text(entity: MonitoringEntity) -> str:
    parts = [
        entity.canonical_name_en or "",
        entity.canonical_name_ar or "",
        entity.semantic_instruction or "",
    ]
    parts.extend(alias.alias_text for alias in entity.aliases)
    return " | ".join(part for part in parts if part)


def _article_text(article: Article) -> str:
    return "\n".join(part for part in (article.title or "", article.body_original or "") if part)


def _entity_terms(entity: MonitoringEntity) -> list[MatchTerm]:
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


def _thresholds(db: Session, tenant_id: UUID) -> tuple[float, float, float]:
    settings = get_settings()
    row = db.scalar(
        select(TenantMatchThreshold).where(TenantMatchThreshold.tenant_id == tenant_id)
    )
    if row:
        return row.min_cosine, row.min_rerank, row.min_classifier
    return settings.semantic_min_cosine, settings.semantic_min_rerank, 0.6


def upsert_article_embedding(db: Session, article: Article) -> ArticleEmbedding:
    settings = get_settings()
    provider = get_embedding_provider(settings)
    text = _article_text(article)
    content_hash = article.content_hash
    existing = db.scalar(
        select(ArticleEmbedding).where(
            ArticleEmbedding.article_id == article.id,
            ArticleEmbedding.provider == provider.name,
            ArticleEmbedding.model == provider.model,
        )
    )
    if existing and existing.content_hash == content_hash:
        return existing
    vector = provider.embed([text], input_type="document")[0]
    if existing is None:
        existing = ArticleEmbedding(
            article_id=article.id,
            provider=provider.name,
            model=provider.model,
            dimensions=provider.dimensions,
            content_hash=content_hash,
            embedding=vector,
        )
        db.add(existing)
    else:
        existing.content_hash = content_hash
        existing.embedding = vector
        existing.dimensions = provider.dimensions
    db.flush()
    return existing


def upsert_entity_embedding(db: Session, entity: MonitoringEntity) -> EntityEmbedding:
    settings = get_settings()
    provider = get_embedding_provider(settings)
    source_text = _entity_query_text(entity)
    existing = db.scalar(
        select(EntityEmbedding).where(
            EntityEmbedding.entity_id == entity.id,
            EntityEmbedding.provider == provider.name,
            EntityEmbedding.model == provider.model,
        )
    )
    vector = provider.embed([source_text], input_type="query")[0]
    if existing is None:
        existing = EntityEmbedding(
            tenant_id=entity.tenant_id,
            entity_id=entity.id,
            provider=provider.name,
            model=provider.model,
            dimensions=provider.dimensions,
            source_text=source_text,
            embedding=vector,
        )
        db.add(existing)
    else:
        existing.source_text = source_text
        existing.embedding = vector
        existing.dimensions = provider.dimensions
    db.flush()
    return existing


def run_semantic_matching_for_tenant(db: Session, *, tenant_id: UUID) -> dict[str, Any]:
    settings = get_settings()
    min_cosine, min_rerank, min_classifier = _thresholds(db, tenant_id)
    embedder = get_embedding_provider(settings)
    reranker = get_rerank_provider(settings)
    llm = get_llm_client(settings)

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
    articles = db.scalars(select(Article)).all()
    if not entities or not articles:
        return {
            "ok": True,
            "tenant_id": str(tenant_id),
            "entities": len(entities),
            "articles": len(articles),
            "candidates_upserted": 0,
            "provider": embedder.name,
            "model": embedder.model,
        }

    article_embeds: dict[UUID, list[float]] = {}
    for article in articles:
        row = upsert_article_embedding(db, article)
        article_embeds[article.id] = list(row.embedding)

    created = 0
    updated = 0
    decisions = 0

    for entity in entities:
        entity_emb = upsert_entity_embedding(db, entity)
        query_vec = list(entity_emb.embedding)
        query_text = entity_emb.source_text

        scored: list[tuple[Article, float]] = []
        for article in articles:
            sim = cosine_similarity(query_vec, article_embeds[article.id])
            if sim >= min_cosine:
                scored.append((article, sim))
        scored.sort(key=lambda item: item[1], reverse=True)
        top = scored[: settings.semantic_top_k]
        if not top:
            continue

        docs = [_article_text(article) for article, _ in top]
        reranked = reranker.rerank(query_text, docs, top_k=settings.semantic_rerank_top_k)
        rerank_map = {item.index: item.score for item in reranked}

        terms = _entity_terms(entity)
        exclusions = [excl.phrase_normalized for excl in entity.exclusions]

        for idx, (article, sim) in enumerate(top):
            rerank_score = rerank_map.get(idx)
            if rerank_score is not None and rerank_score < min_rerank and sim < (min_cosine + 0.15):
                continue

            lexical = match_document(
                title=article.title,
                body=article.body_original,
                terms=terms,
                exclusions_normalized=exclusions,
            )
            if lexical and lexical.excluded:
                continue
            lexical_score = lexical.best_score if lexical else 0.0

            rules_decision = classify_relevance(
                vector_similarity=sim,
                rerank_score=rerank_score,
                lexical_best_score=lexical_score,
                min_classifier=min_classifier,
            )
            if rules_decision.label == "not_relevant":
                continue
            decision = rules_decision
            llm_assessment = None
            llm_error = None
            if rules_decision.label == "needs_review" and llm is not None:
                try:
                    llm_assessment = llm.assess_relevance(
                        entity_query=query_text,
                        article_title=article.title or "",
                        article_body=article.body_original or "",
                    )
                    decision = RelevanceResult(
                        label=llm_assessment.label,
                        confidence=llm_assessment.confidence,
                        reason=llm_assessment.reason,
                        features={
                            **rules_decision.features,
                            "rules_label": rules_decision.label,
                            "rules_confidence": rules_decision.confidence,
                            "llm_provider": llm.name,
                            "llm_model": llm.model,
                        },
                        schema_version="v1",
                        prompt_version="deepseek_relevance_v1",
                    )
                except Exception as exc:  # noqa: BLE001
                    llm_error = str(exc)[:1000]

            provenance = {
                "embedding_provider": embedder.name,
                "embedding_model": embedder.model,
                "rerank_provider": reranker.name,
                "rerank_model": reranker.model,
                "vector_similarity": sim,
                "rerank_score": rerank_score,
                "lexical_best_score": lexical_score,
                "lexical_match_type": lexical.best_match_type if lexical else None,
                "lexical_snippet": lexical.snippet if lexical else None,
                "classifier": {
                    "label": decision.label,
                    "confidence": decision.confidence,
                    "reason": decision.reason,
                    "schema_version": decision.schema_version,
                    "prompt_version": decision.prompt_version,
                },
                "llm_review": {
                    "provider": llm.name if llm_assessment and llm else None,
                    "model": llm.model if llm_assessment and llm else None,
                    "recommendation": llm_assessment.label if llm_assessment else None,
                    "error": llm_error,
                },
                "note": "Semantic retrieval proposes review candidates; never auto-final.",
            }

            existing = db.scalar(
                select(SemanticCandidate).where(
                    SemanticCandidate.tenant_id == tenant_id,
                    SemanticCandidate.entity_id == entity.id,
                    SemanticCandidate.article_id == article.id,
                )
            )
            if existing and existing.status in {"included", "excluded"}:
                continue
            if existing is None:
                existing = SemanticCandidate(
                    tenant_id=tenant_id,
                    entity_id=entity.id,
                    article_id=article.id,
                    vector_similarity=sim,
                    rerank_score=rerank_score,
                    lexical_best_score=lexical_score,
                    classifier_score=decision.confidence,
                    classifier_label=decision.label,
                    status="pending_review",
                    provenance=provenance,
                )
                db.add(existing)
                db.flush()
                created += 1
            else:
                existing.vector_similarity = sim
                existing.rerank_score = rerank_score
                existing.lexical_best_score = lexical_score
                existing.classifier_score = decision.confidence
                existing.classifier_label = decision.label
                existing.status = "pending_review"
                existing.provenance = provenance
                updated += 1

            db.add(
                RelevanceDecision(
                    tenant_id=tenant_id,
                    semantic_candidate_id=existing.id,
                    label=decision.label,
                    confidence=decision.confidence,
                    reason=decision.reason,
                    schema_version=decision.schema_version,
                    prompt_version=decision.prompt_version,
                    features=decision.features,
                )
            )
            decisions += 1

            # Optionally mirror into lexical inbox when classifier says relevant/needs_review
            # but only as pending_review with explainable semantic provenance.
            if decision.label in {"relevant", "needs_review"}:
                _mirror_to_match_inbox(
                    db,
                    tenant_id=tenant_id,
                    entity_id=entity.id,
                    article=article,
                    lexical_score=lexical_score,
                    lexical_term=(
                        lexical.matched_term
                        if lexical
                        else (entity.canonical_name_en or "")
                    ),
                    snippet=(
                        lexical.snippet if lexical else (article.title or "")[:240]
                    ),
                    provenance=provenance,
                )

    db.commit()
    return {
        "ok": True,
        "tenant_id": str(tenant_id),
        "entities": len(entities),
        "articles": len(articles),
        "candidates_created": created,
        "candidates_updated": updated,
        "relevance_decisions": decisions,
        "provider": embedder.name,
        "model": embedder.model,
        "rerank_provider": reranker.name,
        "thresholds": {
            "min_cosine": min_cosine,
            "min_rerank": min_rerank,
            "min_classifier": min_classifier,
        },
    }


def _mirror_to_match_inbox(
    db: Session,
    *,
    tenant_id: UUID,
    entity_id: UUID,
    article: Article,
    lexical_score: float,
    lexical_term: str,
    snippet: str,
    provenance: dict[str, Any],
) -> None:
    existing = db.scalar(
        select(TextMatch).where(
            TextMatch.tenant_id == tenant_id,
            TextMatch.entity_id == entity_id,
            TextMatch.article_id == article.id,
        )
    )
    if existing and existing.status in {"included", "excluded"}:
        return
    match_type = "semantic_assisted" if lexical_score < 0.9 else "semantic_with_lexical"
    if existing is None:
        db.add(
            TextMatch(
                tenant_id=tenant_id,
                entity_id=entity_id,
                article_id=article.id,
                status="pending_review",
                best_match_type=match_type,
                best_score=max(lexical_score, float(provenance.get("vector_similarity") or 0)),
                matched_term=lexical_term or "semantic_candidate",
                matched_term_normalized=normalize_text(lexical_term or "semantic_candidate"),
                snippet=snippet,
            )
        )
    else:
        # Don't downgrade a stronger lexical match type.
        if existing.best_match_type in {
            "exact",
            "case_insensitive_en",
            "arabic_normalized",
            "alias",
        }:
            return
        existing.best_match_type = match_type
        existing.best_score = max(
            existing.best_score, float(provenance.get("vector_similarity") or 0)
        )
        existing.snippet = snippet or existing.snippet
        existing.status = "pending_review"
