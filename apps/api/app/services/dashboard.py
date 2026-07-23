"""Public dashboard payload (no auth) for the live demo UI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.articles import Article
from app.models.epaper import EpaperEdition
from app.models.observability import JobRun
from app.models.sources import Publisher, SourceChannel
from app.services.ingestion_pipeline import article_stats
from app.services.source_enablement import DEFAULT_LOOKBACK_DAYS

INGEST_TASK_NAME = "ingestion.lookback.public"


def _snippet(text: str | None, *, limit: int = 220) -> str | None:
    if not text:
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def build_dashboard(
    db: Session,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    limit: int = 40,
) -> dict[str, Any]:
    stats = article_stats(db, lookback_days=lookback_days)
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

    article_rows = db.execute(
        select(
            Article.id,
            Article.title,
            Article.canonical_url,
            Article.published_at,
            Article.language,
            Article.body_original,
            Article.discovered_at,
            Publisher.code,
            Publisher.name_en,
            Publisher.name_ar,
        )
        .join(Publisher, Publisher.id == Article.publisher_id)
        .order_by(desc(Article.published_at).nulls_last(), desc(Article.discovered_at))
        .limit(limit)
    ).all()

    articles = [
        {
            "id": str(row.id),
            "title": row.title or "(untitled)",
            "url": row.canonical_url,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "discovered_at": row.discovered_at.isoformat() if row.discovered_at else None,
            "language": row.language,
            "has_body": bool(row.body_original),
            "in_lookback": bool(row.published_at and row.published_at >= cutoff),
            "snippet": _snippet(row.body_original),
            "publisher_code": row.code,
            "publisher_name_en": row.name_en,
            "publisher_name_ar": row.name_ar,
        }
        for row in article_rows
    ]

    publisher_rows = db.execute(
        select(
            Publisher.code,
            Publisher.name_en,
            Publisher.name_ar,
            Publisher.homepage_url,
            func.count(SourceChannel.id),
        )
        .outerjoin(SourceChannel, SourceChannel.publisher_id == Publisher.id)
        .group_by(
            Publisher.id,
            Publisher.code,
            Publisher.name_en,
            Publisher.name_ar,
            Publisher.homepage_url,
        )
        .order_by(Publisher.code)
    ).all()

    publishers = [
        {
            "code": code,
            "name_en": name_en,
            "name_ar": name_ar,
            "homepage_url": homepage_url,
            "channel_count": channel_count,
            "article_stats": stats.get("by_publisher", {}).get(code, {}),
        }
        for code, name_en, name_ar, homepage_url, channel_count in publisher_rows
    ]

    edition_rows = db.execute(
        select(
            EpaperEdition.id,
            EpaperEdition.edition_date,
            EpaperEdition.title,
            EpaperEdition.status,
            EpaperEdition.source_url,
            EpaperEdition.page_count,
            Publisher.code,
            Publisher.name_en,
            Publisher.name_ar,
        )
        .join(Publisher, Publisher.id == EpaperEdition.publisher_id)
        .order_by(desc(EpaperEdition.edition_date))
        .limit(12)
    ).all()

    epaper_editions = [
        {
            "id": str(row.id),
            "edition_date": row.edition_date.isoformat(),
            "title": row.title,
            "status": row.status,
            "source_url": row.source_url,
            "page_count": row.page_count,
            "publisher_code": row.code,
            "publisher_name_en": row.name_en,
            "publisher_name_ar": row.name_ar,
        }
        for row in edition_rows
    ]

    latest_ingest = db.scalar(
        select(JobRun)
        .where(JobRun.task_name == INGEST_TASK_NAME)
        .order_by(JobRun.created_at.desc())
        .limit(1)
    )
    ingestion = None
    if latest_ingest is not None:
        result = latest_ingest.result or {}
        ingestion = {
            "id": str(latest_ingest.id),
            "status": str(getattr(latest_ingest.status, "value", latest_ingest.status)),
            "attempt_count": latest_ingest.attempt_count,
            "error": latest_ingest.error_message,
            "created_at": (
                latest_ingest.created_at.isoformat() if latest_ingest.created_at else None
            ),
            "started_at": (
                latest_ingest.started_at.isoformat() if latest_ingest.started_at else None
            ),
            "finished_at": (
                latest_ingest.finished_at.isoformat() if latest_ingest.finished_at else None
            ),
            "result_summary": {
                "stats": result.get("stats"),
                "discovery": {
                    key: (result.get("discovery") or {}).get(key)
                    for key in (
                        "channels_attempted",
                        "channels_ok",
                        "discovered_total",
                        "created_or_updated_total",
                    )
                },
                "fetch": {
                    key: (result.get("fetch") or {}).get(key)
                    for key in ("fetched", "error_count", "stale_dropped")
                },
            }
            if result
            else None,
        }

    return {
        "stats": stats,
        "articles": articles,
        "publishers": publishers,
        "epaper_editions": epaper_editions,
        "ingestion": ingestion,
        "generated_at": datetime.now(UTC).isoformat(),
    }
