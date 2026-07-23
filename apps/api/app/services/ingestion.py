"""Phase 3 gated discovery/ingestion.

Live discovery runs only when:
- assessment.legal_gate == approved
- connector_config.enabled == true
- connector type is implemented
"""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime, timedelta
from html import unescape
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from newsfetcher_connectors.registry import get_connector
from newsfetcher_connectors.types import ConnectorContext, ConnectorType, DiscoveredItem
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.arabic import normalize_text
from app.models.articles import Article, ArticleVersion, StoryCluster, StoryClusterMember
from app.models.enums import LegalGate
from app.models.sources import (
    Publisher,
    SourceChannel,
    SourceConnectorConfig,
    SourceFailure,
    SourceFetchRun,
)


def normalize_url(url: str) -> str:
    """Canonicalize for dedupe: unescape entities, keep identity query keys, drop junk."""
    from urllib.parse import parse_qsl, urlencode

    cleaned = unescape((url or "").strip())
    parts = urlsplit(cleaned)
    host = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    keep: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        kl = key.lower()
        if kl in {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "yearquarter"}:
            continue
        if kl in {"id", "language"}:
            keep.append((kl, value.lower() if kl == "language" else value))
    keep.sort()
    query = urlencode(keep, doseq=True)
    return urlunsplit((parts.scheme.lower(), host, path, query, ""))


def _archive_year_from_url(url: str) -> int | None:
    match = re.search(r"[?&]yearquarter=(\d{4,})", unescape(url or ""), flags=re.I)
    if not match:
        return None
    try:
        return int(match.group(1)[:4])
    except ValueError:
        return None


def title_fingerprint(title: str | None) -> str:
    normalized = normalize_text(title or "")
    return hashlib.sha256(normalized.encode()).hexdigest()


def _clip(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _parse_item_published_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except ValueError:
            continue
    return None


def channel_ingestion_allowed(
    channel: SourceChannel, connector: SourceConnectorConfig
) -> tuple[bool, str]:
    if channel.assessment is None:
        return False, "missing_assessment"
    if channel.assessment.legal_gate != LegalGate.approved:
        return False, "legal_gate_pending"
    if not connector.enabled:
        return False, "connector_disabled"
    connector_type = str(
        getattr(connector.connector_type, "value", connector.connector_type)
    )
    if connector_type in {"pending", "blocked"}:
        return False, "connector_not_configured"
    return True, "ok"


def discover_channel(db: Session, channel_id: Any) -> dict[str, Any]:
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

    allowed, reason = channel_ingestion_allowed(channel, connector_cfg)
    run = SourceFetchRun(
        id=uuid4(),
        source_channel_id=channel.id,
        status="running",
        started_at=datetime.now(UTC),
        meta={"phase": 3, "gate_reason": reason},
    )
    db.add(run)
    db.flush()

    if not allowed:
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        run.error_summary = reason
        db.add(
            SourceFailure(
                source_channel_id=channel.id,
                fetch_run_id=run.id,
                failure_type="ingestion_gate",
                message=reason,
                details={
                    "legal_gate": (
                        str(channel.assessment.legal_gate) if channel.assessment else None
                    )
                },
            )
        )
        db.commit()
        return {"ok": False, "reason": reason, "fetch_run_id": str(run.id)}

    publisher: Publisher = channel.publisher
    connector_type = ConnectorType(
        str(getattr(connector_cfg.connector_type, "value", connector_cfg.connector_type))
    )
    context = ConnectorContext(
        publisher_code=publisher.code,
        channel_code=channel.code,
        base_url=channel.base_url,
        language=str(getattr(channel.language, "value", channel.language)),
        config=connector_cfg.config or {},
        politeness_delay_ms=connector_cfg.politeness_delay_ms,
        max_requests_per_minute=connector_cfg.max_requests_per_minute,
    )

    lookback_days = (connector_cfg.config or {}).get("lookback_days")
    cutoff = None
    if lookback_days is not None:
        cutoff = datetime.now(UTC) - timedelta(days=int(lookback_days))

    try:
        if connector_type == ConnectorType.epaper:
            from app.services.epaper import discover_and_ingest_epaper_editions

            epaper_result = discover_and_ingest_epaper_editions(
                db,
                channel_id=channel.id,
                actor_id=None,
                download=True,
            )
            run.status = "succeeded" if epaper_result.get("ok") else "failed"
            run.items_discovered = int(epaper_result.get("discovered") or 0)
            run.items_fetched = int(epaper_result.get("ingested") or 0)
            run.finished_at = datetime.now(UTC)
            run.error_summary = None if epaper_result.get("ok") else str(
                epaper_result.get("reason") or "epaper_ingest_failed"
            )
            run.meta = {
                **run.meta,
                "epaper": epaper_result,
                "lookback_days": lookback_days,
            }
            db.commit()
            return {
                "ok": bool(epaper_result.get("ok")),
                "fetch_run_id": str(run.id),
                "discovered": run.items_discovered,
                "created_or_updated": run.items_fetched,
                "epaper": epaper_result,
            }

        result = get_connector(connector_type).discover(context)
        created = 0
        skipped_stale = 0
        for item in result.items:
            published_at = _parse_item_published_at(item.published_at)
            if cutoff is not None and published_at is not None and published_at < cutoff:
                skipped_stale += 1
                continue
            if _upsert_discovered_article(
                db, channel, publisher, item, published_at=published_at
            ):
                created += 1
        run.status = "succeeded"
        run.items_discovered = len(result.items)
        run.items_fetched = created
        run.finished_at = datetime.now(UTC)
        run.meta = {
            **run.meta,
            "errors": result.errors,
            "connector_meta": result.meta,
            "lookback_days": lookback_days,
            "skipped_stale": skipped_stale,
        }
        db.commit()
        return {
            "ok": True,
            "fetch_run_id": str(run.id),
            "discovered": len(result.items),
            "created_or_updated": created,
            "skipped_stale": skipped_stale,
            "errors": result.errors,
        }
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        run = SourceFetchRun(
            id=uuid4(),
            source_channel_id=channel_id,
            status="failed",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            error_summary=str(exc)[:2000],
            meta={"phase": 3, "gate_reason": "discovery_exception"},
        )
        db.add(run)
        db.flush()
        db.add(
            SourceFailure(
                source_channel_id=channel_id,
                fetch_run_id=run.id,
                failure_type="discovery_exception",
                message=str(exc)[:2000],
                details={},
            )
        )
        db.commit()
        return {"ok": False, "reason": str(exc), "fetch_run_id": str(run.id)}


def _upsert_discovered_article(
    db: Session,
    channel: SourceChannel,
    publisher: Publisher,
    item: DiscoveredItem,
    *,
    published_at: datetime | None = None,
) -> bool:
    canonical = unescape(item.canonical_url or item.source_url or "")
    source_url = unescape(item.source_url or canonical)
    # Drop Al-Watan archive quarter links older than last year (discovery noise).
    archive_year = _archive_year_from_url(source_url) or _archive_year_from_url(canonical)
    if archive_year is not None and archive_year < datetime.now(UTC).year - 1:
        return False

    normalized = normalize_url(canonical)
    # Dedupe across channels for the same publisher (KUNA multi-feed duplicates).
    existing = db.scalar(
        select(Article).where(
            Article.publisher_id == publisher.id,
            Article.normalized_url == normalized,
        )
    )
    content_hash = item.content_hash or hashlib.sha256(canonical.encode()).hexdigest()
    title = _clip(item.title, 1024)
    t_hash = title_fingerprint(title)

    if existing is None:
        cluster = db.scalar(select(StoryCluster).where(StoryCluster.title_fingerprint == t_hash))
        if cluster is None and title:
            cluster = StoryCluster(
                title_fingerprint=t_hash,
                representative_title=_clip(title, 512),
            )
            db.add(cluster)
            db.flush()

        article = Article(
            publisher_id=publisher.id,
            source_channel_id=channel.id,
            canonical_url=_clip(canonical, 2048) or canonical,
            source_url=_clip(source_url, 2048) or source_url,
            title=title,
            language=item.language or str(getattr(channel.language, "value", channel.language)),
            content_hash=content_hash,
            title_hash=t_hash,
            normalized_url=_clip(normalized, 2048) or normalized,
            published_at=published_at,
            story_cluster_id=cluster.id if cluster else None,
            metadata_={"discovery": item.metadata, "phase": 3},
            discovered_at=datetime.now(UTC),
        )
        db.add(article)
        db.flush()
        db.add(
            ArticleVersion(
                article_id=article.id,
                version_number=1,
                title=title,
                content_hash=content_hash,
                raw_snapshot=item.model_dump(),
            )
        )
        if cluster is not None:
            db.add(
                StoryClusterMember(
                    story_cluster_id=cluster.id,
                    article_id=article.id,
                )
            )
        return True

    # Existing article: keep provenance; do not delete cross-publication duplicates.
    existing.title = title or existing.title
    existing.content_hash = content_hash
    if published_at is not None:
        existing.published_at = published_at
    existing.metadata_ = {**(existing.metadata_ or {}), "last_discovery": item.metadata}
    return False
