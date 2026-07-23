"""Public no-auth dashboard endpoints for the live demo UI."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.enums import JobRunStatus
from app.models.observability import JobRun
from app.services.dashboard import build_dashboard

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
INGEST_TASK_NAME = "ingestion.lookback.public"
INGEST_QUEUE = "source.discovery"


def _require_public_dashboard() -> None:
    if not get_settings().demo_public_dashboard:
        raise HTTPException(status_code=404, detail="Public dashboard disabled")


@router.get("")
def get_dashboard(
    lookback_days: int = Query(default=5, ge=1, le=30),
    limit: int = Query(default=40, ge=1, le=100),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_public_dashboard()
    return build_dashboard(db, lookback_days=lookback_days, limit=limit)


def _job_out(job: JobRun) -> dict[str, Any]:
    status = str(getattr(job.status, "value", job.status))
    return {
        "id": str(job.id),
        "status": status,
        "attempt_count": job.attempt_count,
        "error": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "result": job.result,
    }


@router.post("/ingest", status_code=202)
def trigger_public_ingest(
    lookback_days: int = Query(default=5, ge=1, le=14),
    fetch_limit: int = Query(default=400, ge=50, le=1200),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_public_dashboard()
    if not get_settings().demo_public_ingest:
        raise HTTPException(status_code=403, detail="Public ingest disabled")

    latest = db.scalar(
        select(JobRun)
        .where(JobRun.task_name == INGEST_TASK_NAME)
        .order_by(JobRun.created_at.desc())
        .limit(1)
    )
    if latest is not None and latest.status in {JobRunStatus.queued, JobRunStatus.running}:
        return {
            "status": str(getattr(latest.status, "value", latest.status)),
            "message": "An ingest is already queued or running.",
            "ingestion": _job_out(latest),
        }
    if (
        latest is not None
        and latest.status == JobRunStatus.succeeded
        and latest.finished_at is not None
        and latest.finished_at >= datetime.now(UTC) - timedelta(minutes=15)
    ):
        return {
            "status": "succeeded",
            "message": "The news index was refreshed recently.",
            "ingestion": _job_out(latest),
        }

    job = JobRun(
        queue_name=INGEST_QUEUE,
        task_name=INGEST_TASK_NAME,
        status=JobRunStatus.queued,
        payload={"lookback_days": lookback_days, "fetch_limit": fetch_limit},
        result={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        from app.workers.tasks import run_public_lookback_ingest

        run_public_lookback_ingest.apply_async(
            args=[str(job.id), lookback_days, fetch_limit],
            queue=INGEST_QUEUE,
        )
    except Exception as exc:
        job.status = JobRunStatus.failed
        job.error_message = f"Could not queue ingest: {exc}"[:4000]
        job.finished_at = datetime.now(UTC)
        db.commit()
        raise HTTPException(status_code=503, detail=job.error_message) from exc

    return {
        "status": "queued",
        "lookback_days": lookback_days,
        "fetch_limit": fetch_limit,
        "message": "Ingest queued. The dashboard will update as the worker runs.",
        "ingestion": _job_out(job),
    }
