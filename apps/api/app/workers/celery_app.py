from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "newsfetcher",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Queue names reserved for later phases — registered now for architecture baseline.
QUEUE_NAMES = (
    "source.discovery",
    "article.fetch",
    "article.parse",
    "article.normalize",
    "article.deduplicate",
    "epaper.discover",
    "epaper.download",
    "epaper.render",
    "ocr.process",
    "embedding.generate",
    "matching.lexical",
    "matching.semantic",
    "matching.rerank",
    "matching.classify",
    "cutting.generate",
    "logo.detect",
    "social.poll",
    "report.prepare",
    "report.render",
    "report.deliver",
    "source.health",
)

celery_app.conf.update(
    task_default_queue="source.health",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_soft_time_limit=1800,
    task_time_limit=2100,
    broker_connection_retry_on_startup=True,
    imports=("app.workers.tasks",),
    task_routes={
        "app.workers.tasks.ping_source_health": {"queue": "source.health"},
        "app.workers.tasks.probe_all_source_health": {"queue": "source.health"},
        "app.workers.tasks.discover_source_channel": {"queue": "source.discovery"},
        "app.workers.tasks.discover_all_enabled_sources": {"queue": "source.discovery"},
        "app.workers.tasks.fetch_article_bodies_task": {"queue": "article.fetch"},
        "app.workers.tasks.run_lookback_ingest_task": {"queue": "source.discovery"},
        "app.workers.tasks.run_public_lookback_ingest": {"queue": "source.discovery"},
        "app.workers.tasks.enrich_recent_article_assets": {"queue": "matching.classify"},
        "app.workers.tasks.run_lexical_matching": {"queue": "matching.lexical"},
        "app.workers.tasks.run_semantic_matching": {"queue": "matching.semantic"},
        "app.workers.tasks.run_semantic_rerank": {"queue": "matching.rerank"},
        "app.workers.tasks.render_report": {"queue": "report.render"},
        "app.workers.tasks.deliver_report": {"queue": "report.deliver"},
        "app.workers.tasks.generate_cuttings": {"queue": "cutting.generate"},
        "app.workers.tasks.detect_logos": {"queue": "logo.detect"},
        "app.workers.tasks.poll_social": {"queue": "social.poll"},
    },
)
