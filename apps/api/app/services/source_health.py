from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from newsfetcher_connectors.registry import get_connector
from newsfetcher_connectors.types import ConnectorContext, ConnectorType
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import JobRunStatus
from app.models.observability import JobRun
from app.models.sources import (
    Publisher,
    SourceChannel,
    SourceConnectorConfig,
    SourceFailure,
    SourceFetchRun,
)


def list_source_health(db: Session) -> list[dict[str, Any]]:
    publishers = db.scalars(
        select(Publisher)
        .options(
            selectinload(Publisher.channels).selectinload(SourceChannel.assessment),
            selectinload(Publisher.channels).selectinload(SourceChannel.connector_config),
        )
        .order_by(Publisher.name_en)
    ).all()

    rows: list[dict[str, Any]] = []
    for publisher in publishers:
        for channel in publisher.channels:
            latest_run = db.scalar(
                select(SourceFetchRun)
                .where(SourceFetchRun.source_channel_id == channel.id)
                .order_by(desc(SourceFetchRun.created_at))
                .limit(1)
            )
            recent_failures = db.scalars(
                select(SourceFailure)
                .where(SourceFailure.source_channel_id == channel.id)
                .order_by(desc(SourceFailure.created_at))
                .limit(5)
            ).all()
            assessment = channel.assessment
            connector = channel.connector_config
            rows.append(
                {
                    "publisher_code": publisher.code,
                    "publisher_name_en": publisher.name_en,
                    "channel_code": channel.code,
                    "language": str(getattr(channel.language, "value", channel.language)),
                    "is_active": channel.is_active,
                    "assessment_status": (
                        str(getattr(assessment.status, "value", assessment.status))
                        if assessment
                        else None
                    ),
                    "legal_gate": (
                        str(getattr(assessment.legal_gate, "value", assessment.legal_gate))
                        if assessment
                        else None
                    ),
                    "connector_type": (
                        str(getattr(connector.connector_type, "value", connector.connector_type))
                        if connector
                        else None
                    ),
                    "connector_enabled": connector.enabled if connector else False,
                    "latest_fetch_run": (
                        {
                            "id": str(latest_run.id),
                            "status": latest_run.status,
                            "items_discovered": latest_run.items_discovered,
                            "error_summary": latest_run.error_summary,
                            "created_at": latest_run.created_at.isoformat()
                            if latest_run.created_at
                            else None,
                        }
                        if latest_run
                        else None
                    ),
                    "recent_failure_count": len(recent_failures),
                }
            )
    return rows


def probe_channel_health(db: Session, channel: SourceChannel) -> dict[str, Any]:
    connector_cfg = db.scalar(
        select(SourceConnectorConfig).where(SourceConnectorConfig.source_channel_id == channel.id)
    )
    connector_type = (
        str(getattr(connector_cfg.connector_type, "value", connector_cfg.connector_type))
        if connector_cfg
        else "html"
    )
    if connector_type in {"pending", "blocked"}:
        connector_type = "html"

    publisher = db.get(Publisher, channel.publisher_id)
    assert publisher is not None

    context = ConnectorContext(
        publisher_code=publisher.code,
        channel_code=channel.code,
        base_url=channel.base_url,
        language=str(getattr(channel.language, "value", channel.language)),
        config=connector_cfg.config if connector_cfg else {},
        politeness_delay_ms=connector_cfg.politeness_delay_ms if connector_cfg else 1000,
        max_requests_per_minute=connector_cfg.max_requests_per_minute if connector_cfg else 10,
    )
    connector = get_connector(ConnectorType(connector_type))
    probe = connector.health_probe(context)

    run = SourceFetchRun(
        id=uuid4(),
        source_channel_id=channel.id,
        status="succeeded" if probe.get("ok") else "failed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        items_discovered=0,
        items_fetched=0,
        error_summary=None if probe.get("ok") else str(probe.get("error") or probe),
        meta={"probe": probe, "phase": 1},
    )
    db.add(run)

    job = JobRun(
        id=uuid4(),
        queue_name="source.health",
        task_name="source.health.probe",
        idempotency_key=f"source-health:{channel.id}:{datetime.now(UTC).strftime('%Y%m%d%H%M')}",
        status=JobRunStatus.succeeded if probe.get("ok") else JobRunStatus.failed,
        payload={"channel_id": str(channel.id)},
        result=probe,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        attempt_count=1,
    )
    db.add(job)

    if not probe.get("ok"):
        db.add(
            SourceFailure(
                source_channel_id=channel.id,
                fetch_run_id=run.id,
                failure_type="health_probe",
                message=str(probe.get("error") or "health probe failed"),
                details=probe,
            )
        )
    db.commit()
    return {"channel_id": str(channel.id), "probe": probe, "fetch_run_id": str(run.id)}
