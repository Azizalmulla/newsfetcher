"""Persist DeepSeek article intelligence in article metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.articles import Article
from app.services.llm import get_llm_client


def enrich_recent_articles(db: Session, *, limit: int = 80) -> dict[str, Any]:
    client = get_llm_client()
    if client is None:
        return {
            "ok": False,
            "reason": "deepseek_not_configured",
            "processed": 0,
            "enriched": 0,
        }

    candidates = list(
        db.scalars(
            select(Article)
            .where(Article.body_original.is_not(None))
            .order_by(Article.published_at.desc().nulls_last(), Article.discovered_at.desc())
            .limit(max(limit * 4, limit))
        ).all()
    )
    pending = [
        article
        for article in candidates
        if ((article.metadata_ or {}).get("ai") or {}).get("model") != client.model
    ][:limit]

    enriched = 0
    errors: list[str] = []
    for article in pending:
        try:
            intelligence = client.enrich_article(
                title=article.title or "",
                body=article.body_original or "",
                language=article.language,
            )
            metadata = {**(article.metadata_ or {})}
            metadata["ai"] = {
                "provider": client.name,
                "model": client.model,
                "summary": intelligence.summary,
                "topics": intelligence.topics,
                "sentiment": intelligence.sentiment,
                "importance": intelligence.importance,
                "language": intelligence.language,
                "generated_at": datetime.now(UTC).isoformat(),
                "human_reviewed": False,
            }
            article.metadata_ = metadata
            enriched += 1
            if enriched % 5 == 0:
                db.commit()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{article.id}: {exc}")
    db.commit()
    return {
        "ok": not errors,
        "provider": client.name,
        "model": client.model,
        "processed": len(pending),
        "enriched": enriched,
        "error_count": len(errors),
        "errors": errors[:20],
    }
