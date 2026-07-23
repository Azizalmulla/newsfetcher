"""Production discover → fetch pipeline for enabled sources."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.articles import Article
from app.models.sources import Publisher, SourceChannel, SourceConnectorConfig
from app.services.article_fetch import fetch_article_bodies
from app.services.audit import write_audit
from app.services.ingestion import discover_channel
from app.services.source_enablement import DEFAULT_LOOKBACK_DAYS, enable_web_sources


def discover_all_enabled(
    db: Session,
    *,
    excluded_publisher_codes: set[str] | None = None,
) -> dict[str, Any]:
    stmt = (
        select(SourceChannel)
        .join(
            SourceConnectorConfig,
            SourceConnectorConfig.source_channel_id == SourceChannel.id,
        )
        .where(SourceConnectorConfig.enabled.is_(True))
        .options(
            selectinload(SourceChannel.publisher),
            selectinload(SourceChannel.assessment),
            selectinload(SourceChannel.connector_config),
        )
        .order_by(SourceChannel.code)
    )
    if excluded_publisher_codes:
        stmt = stmt.join(Publisher, Publisher.id == SourceChannel.publisher_id).where(
            Publisher.code.not_in(excluded_publisher_codes)
        )
    channels = db.scalars(stmt).all()

    results: list[dict[str, Any]] = []
    ok_count = 0
    discovered_total = 0
    created_total = 0
    for channel in channels:
        publisher = channel.publisher
        try:
            result = discover_channel(db, channel.id)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            result = {"ok": False, "reason": str(exc)}
        row = {
            "publisher": publisher.code if publisher else None,
            "channel": channel.code,
            **result,
        }
        results.append(row)
        if result.get("ok"):
            ok_count += 1
            discovered_total += int(result.get("discovered") or 0)
            created_total += int(result.get("created_or_updated") or 0)

    return {
        "channels_attempted": len(channels),
        "channels_ok": ok_count,
        "discovered_total": discovered_total,
        "created_or_updated_total": created_total,
        "results": results,
    }


def article_stats(db: Session, *, lookback_days: int = DEFAULT_LOOKBACK_DAYS) -> dict[str, Any]:
    from datetime import UTC, datetime, timedelta

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    total = db.scalar(select(func.count()).select_from(Article)) or 0
    with_body = (
        db.scalar(
            select(func.count()).select_from(Article).where(Article.body_original.is_not(None))
        )
        or 0
    )
    with_date = (
        db.scalar(
            select(func.count()).select_from(Article).where(Article.published_at.is_not(None))
        )
        or 0
    )
    confirmed = (
        db.scalar(
            select(func.count())
            .select_from(Article)
            .where(
                Article.body_original.is_not(None),
                Article.published_at.is_not(None),
                Article.published_at >= cutoff,
            )
        )
        or 0
    )
    date_unknown = (
        db.scalar(
            select(func.count())
            .select_from(Article)
            .where(
                Article.body_original.is_not(None),
                Article.published_at.is_(None),
            )
        )
        or 0
    )
    by_publisher_rows = db.execute(
        select(
            Publisher.code,
            func.count(),
            func.count(Article.body_original),
            func.count(Article.published_at),
            func.count().filter(
                Article.body_original.is_not(None),
                Article.published_at.is_not(None),
                Article.published_at >= cutoff,
            ),
            func.count().filter(
                Article.body_original.is_not(None),
                Article.published_at.is_(None),
            ),
        )
        .select_from(Article)
        .join(Publisher, Publisher.id == Article.publisher_id)
        .group_by(Publisher.code)
        .order_by(Publisher.code)
    ).all()
    return {
        "articles_total": total,
        "articles_with_body": with_body,
        "articles_with_date": with_date,
        "confirmed_in_lookback": confirmed,
        "date_unknown_with_body": date_unknown,
        "lookback_days": lookback_days,
        "by_publisher": {
            code: {
                "total": total_count,
                "with_body": body_count,
                "with_date": dated_count,
                "confirmed_in_lookback": confirmed_count,
                "date_unknown_with_body": unknown_count,
            }
            for (
                code,
                total_count,
                body_count,
                dated_count,
                confirmed_count,
                unknown_count,
            ) in by_publisher_rows
        },
    }


def run_lookback_ingest(
    db: Session,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    fetch_limit: int = 800,
    actor_id: str | None = None,
    include_temporarily_broken: bool = True,
    enable_first: bool = True,
    use_browser_fallback: bool = True,
    excluded_publisher_codes: set[str] | None = None,
) -> dict[str, Any]:
    enable_result = None
    if enable_first:
        enable_result = enable_web_sources(
            db,
            lookback_days=lookback_days,
            actor_id=actor_id,
            include_temporarily_broken=include_temporarily_broken,
        )
    discovery = discover_all_enabled(
        db,
        excluded_publisher_codes=excluded_publisher_codes,
    )
    fetch = fetch_article_bodies(
        db,
        lookback_days=lookback_days,
        limit=fetch_limit,
        politeness_delay_ms=400,
        max_requests_per_minute=45,
        commit_every=20,
        use_browser_fallback=use_browser_fallback,
        excluded_publisher_codes=excluded_publisher_codes,
    )
    stats = article_stats(db)
    write_audit(
        db,
        tenant_id=None,
        actor_id=actor_id,
        action="ingestion.lookback_run_completed",
        resource_type="ingestion",
        resource_id="web_lookback",
        details={
            "lookback_days": lookback_days,
            "discovery": {
                "channels_ok": discovery["channels_ok"],
                "discovered_total": discovery["discovered_total"],
                "created_or_updated_total": discovery["created_or_updated_total"],
            },
            "fetch": {
                "fetched": fetch["fetched"],
                "stale_dropped": fetch["stale_dropped"],
                "error_count": fetch["error_count"],
                "browser_fetches": fetch.get("browser_fetches"),
            },
            "stats": stats,
        },
    )
    db.commit()
    return {
        "lookback_days": lookback_days,
        "enable": enable_result,
        "discovery": discovery,
        "fetch": fetch,
        "stats": stats,
    }


# Back-compat for older script names.
run_demo_five_day_scrape = run_lookback_ingest
