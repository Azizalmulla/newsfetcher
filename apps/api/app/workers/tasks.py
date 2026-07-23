"""Celery tasks.

Phase 1: source health probes only. Discovery/fetch require legal_gate + enabled config.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.enums import JobRunStatus
from app.models.observability import JobRun
from app.models.sources import Publisher, SourceChannel
from app.services.ai_enrichment import enrich_recent_articles as enrich_recent_articles_service
from app.services.article_fetch import backfill_article_images, fetch_article_bodies
from app.services.epaper import propose_cuttings_for_tenant
from app.services.ingestion import discover_channel
from app.services.ingestion_pipeline import discover_all_enabled, run_lookback_ingest
from app.services.logos import run_detect_and_propose
from app.services.matching import match_all_articles_for_tenant, match_article_for_tenant
from app.services.reports import approve_and_render, deliver_version
from app.services.semantic_matching import run_semantic_matching_for_tenant
from app.services.social import poll_approved_accounts
from app.services.source_enablement import enable_web_sources
from app.services.source_health import list_source_health, probe_channel_health
from app.workers.celery_app import celery_app

PRIORITY_SOURCE_RECOVERY: tuple[tuple[str, bool], ...] = (
    ("kuna", False),
    ("alseyassah", False),
    ("alwasat", False),
    ("alwatan", True),
)


@celery_app.task(name="app.workers.tasks.ping_source_health")  # type: ignore[untyped-decorator]
def ping_source_health() -> dict[str, object]:
    db = SessionLocal()
    try:
        rows = list_source_health(db)
        return {
            "status": "ok",
            "phase": "1",
            "ingestion": "disabled_until_legal_gate",
            "channel_count": len(rows),
            "enabled_connectors": sum(1 for row in rows if row["connector_enabled"]),
        }
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.probe_all_source_health")  # type: ignore[untyped-decorator]
def probe_all_source_health() -> dict[str, object]:
    """Polite homepage/health probes for all channels. Does not enable ingestion."""
    db = SessionLocal()
    results = []
    try:
        channels = db.scalars(select(SourceChannel)).all()
        for channel in channels:
            results.append(probe_channel_health(db, channel))
        return {"probed": len(results), "results": results}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.discover_source_channel")  # type: ignore[untyped-decorator]
def discover_source_channel(channel_id: str) -> dict[str, object]:
    """Queue: source.discovery — gated by legal_gate + connector.enabled."""
    db = SessionLocal()
    try:
        return discover_channel(db, channel_id)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.discover_all_enabled_sources")  # type: ignore[untyped-decorator]
def discover_all_enabled_sources() -> dict[str, object]:
    """Queue: source.discovery — discover every enabled connector."""
    db = SessionLocal()
    try:
        return discover_all_enabled(db)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.fetch_article_bodies_task")  # type: ignore[untyped-decorator]
def fetch_article_bodies_task(
    lookback_days: int = 5, limit: int = 500, use_browser_fallback: bool = True
) -> dict[str, object]:
    """Queue: article.fetch — fill bodies for discovered articles."""
    db = SessionLocal()
    try:
        return fetch_article_bodies(
            db,
            lookback_days=lookback_days,
            limit=limit,
            use_browser_fallback=use_browser_fallback,
        )
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.recover_publisher_articles")  # type: ignore[untyped-decorator]
def recover_publisher_articles(
    publisher_code: str,
    limit: int = 150,
    use_browser_fallback: bool = False,
) -> dict[str, object]:
    """Discover and fetch one publisher without blocking the main coverage update."""
    db = SessionLocal()
    try:
        publisher = db.scalar(select(Publisher).where(Publisher.code == publisher_code))
        if publisher is None:
            return {"ok": False, "reason": "publisher_not_found", "publisher": publisher_code}
        channels = db.scalars(
            select(SourceChannel).where(SourceChannel.publisher_id == publisher.id)
        ).all()
        discovery = [discover_channel(db, channel.id) for channel in channels]
        fetch = fetch_article_bodies(
            db,
            lookback_days=5,
            limit=limit,
            politeness_delay_ms=300,
            max_requests_per_minute=60,
            use_browser_fallback=use_browser_fallback,
            publisher_codes={publisher_code},
        )
        return {
            "ok": True,
            "publisher": publisher_code,
            "discovery": discovery,
            "fetch": fetch,
        }
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_lookback_ingest_task")  # type: ignore[untyped-decorator]
def run_lookback_ingest_task(
    lookback_days: int = 5,
    fetch_limit: int = 800,
    enable_first: bool = False,
) -> dict[str, object]:
    """Queue: full lookback ingest. enable_first=False for scheduled runs."""
    db = SessionLocal()
    try:
        return run_lookback_ingest(
            db,
            lookback_days=lookback_days,
            fetch_limit=fetch_limit,
            actor_id="celery",
            enable_first=enable_first,
            use_browser_fallback=True,
        )
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_public_lookback_ingest")  # type: ignore[untyped-decorator]
def run_public_lookback_ingest(
    job_id: str,
    lookback_days: int = 5,
    fetch_limit: int = 400,
) -> dict[str, object]:
    """Run the public demo ingest and persist truthful job state for the dashboard."""
    db = SessionLocal()
    job_uuid = UUID(job_id)
    try:
        job = db.get(JobRun, job_uuid)
        if job is None:
            raise ValueError(f"Ingest job {job_id} does not exist")
        job.status = JobRunStatus.running
        job.started_at = datetime.now(UTC)
        job.attempt_count += 1
        db.commit()

        enable_result = enable_web_sources(
            db,
            lookback_days=lookback_days,
            actor_id="public-demo-worker",
            include_temporarily_broken=True,
        )
        for publisher_code, browser_required in PRIORITY_SOURCE_RECOVERY:
            recover_publisher_articles.apply_async(
                kwargs={
                    "publisher_code": publisher_code,
                    "limit": 150,
                    "use_browser_fallback": browser_required,
                },
                queue="article.fetch",
            )

        result = run_lookback_ingest(
            db,
            lookback_days=lookback_days,
            fetch_limit=fetch_limit,
            actor_id="public-demo-worker",
            enable_first=False,
            # Browser-only sources run separately; never let Playwright block the whole demo sync.
            use_browser_fallback=False,
            excluded_publisher_codes={
                publisher_code for publisher_code, _ in PRIORITY_SOURCE_RECOVERY
            },
        )
        result["enable"] = enable_result
        job = db.get(JobRun, job_uuid)
        if job is None:
            raise ValueError(f"Ingest job {job_id} disappeared")
        job.status = JobRunStatus.succeeded
        job.result = result
        job.finished_at = datetime.now(UTC)
        job.error_message = None
        db.commit()
        enrich_recent_article_assets.apply_async(
            kwargs={"image_limit": fetch_limit, "llm_limit": min(fetch_limit, 80)},
            queue="matching.classify",
        )
        return dict(result)
    except Exception as exc:
        db.rollback()
        job = db.get(JobRun, job_uuid)
        if job is not None:
            job.status = JobRunStatus.failed
            job.error_message = str(exc)[:4000]
            job.finished_at = datetime.now(UTC)
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.enrich_recent_article_assets")  # type: ignore[untyped-decorator]
def enrich_recent_article_assets(
    image_limit: int = 300,
    llm_limit: int = 80,
) -> dict[str, object]:
    """Backfill real publisher covers, then add DeepSeek summaries and topics."""
    db = SessionLocal()
    try:
        images = backfill_article_images(db, limit=image_limit)
        intelligence = enrich_recent_articles_service(db, limit=llm_limit)
        return {"images": images, "intelligence": intelligence}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_lexical_matching")  # type: ignore[untyped-decorator]
def run_lexical_matching(tenant_id: str, article_id: str | None = None) -> dict[str, object]:
    """Queue: matching.lexical — deterministic layers only."""
    db = SessionLocal()
    try:
        tid = UUID(tenant_id)
        if article_id:
            return match_article_for_tenant(db, tenant_id=tid, article_id=UUID(article_id))
        return match_all_articles_for_tenant(db, tenant_id=tid)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_semantic_matching")  # type: ignore[untyped-decorator]
def run_semantic_matching(tenant_id: str) -> dict[str, object]:
    """Queue: matching.semantic — retrieval + rerank + classifier → review."""
    db = SessionLocal()
    try:
        return run_semantic_matching_for_tenant(db, tenant_id=UUID(tenant_id))
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_semantic_rerank")  # type: ignore[untyped-decorator]
def run_semantic_rerank(tenant_id: str) -> dict[str, object]:
    """Alias queue entrypoint; full semantic pipeline includes rerank."""
    result = run_semantic_matching(tenant_id)
    return dict(result)


@celery_app.task(name="app.workers.tasks.render_report")  # type: ignore[untyped-decorator]
def render_report(tenant_id: str, report_id: str, actor_id: str) -> dict[str, object]:
    """Queue: report.render — approve draft and persist immutable PDF version."""
    db = SessionLocal()
    try:
        report = approve_and_render(
            db,
            tenant_id=UUID(tenant_id),
            report_id=UUID(report_id),
            actor_id=UUID(actor_id),
        )
        latest = (
            max(report.versions, key=lambda row: row.version_number)
            if report.versions
            else None
        )
        return {
            "report_id": str(report.id),
            "status": report.status,
            "version": latest.version_number if latest else None,
            "content_hash": latest.content_hash if latest else None,
        }
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.generate_cuttings")  # type: ignore[untyped-decorator]
def generate_cuttings(tenant_id: str, edition_id: str) -> dict[str, object]:
    """Queue: cutting.generate — propose e-paper cuttings for a tenant."""
    db = SessionLocal()
    try:
        return propose_cuttings_for_tenant(
            db, tenant_id=UUID(tenant_id), edition_id=UUID(edition_id)
        )
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.poll_social")  # type: ignore[untyped-decorator]
def poll_social(actor_id: str | None = None) -> dict[str, object]:
    """Queue: social.poll — official X API only; fails closed when gates incomplete."""
    db = SessionLocal()
    try:
        return poll_approved_accounts(db, actor_id=actor_id)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.detect_logos")  # type: ignore[untyped-decorator]
def detect_logos(
    tenant_id: str,
    actor_id: str,
    page_id: str | None = None,
    article_image_id: str | None = None,
) -> dict[str, object]:
    """Queue: logo.detect — cascade screen → propose matches (never auto-final)."""
    db = SessionLocal()
    try:
        return run_detect_and_propose(
            db,
            tenant_id=UUID(tenant_id),
            actor_id=UUID(actor_id),
            page_id=UUID(page_id) if page_id else None,
            article_image_id=UUID(article_image_id) if article_image_id else None,
        )
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.deliver_report")  # type: ignore[untyped-decorator]
def deliver_report(
    tenant_id: str,
    report_id: str,
    version_number: int,
    actor_id: str,
    recipients: list[str],
) -> dict[str, object]:
    """Queue: report.deliver — email an immutable PDF version."""
    db = SessionLocal()
    try:
        version = deliver_version(
            db,
            tenant_id=UUID(tenant_id),
            report_id=UUID(report_id),
            version_number=version_number,
            actor_id=UUID(actor_id),
            recipients=recipients,
        )
        return {
            "report_id": report_id,
            "version": version.version_number,
            "email_status": version.email_status,
            "recipients": version.email_recipients,
        }
    finally:
        db.close()
