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
INGEST_PENDING_GRACE = timedelta(minutes=5)
INGEST_LEGACY_GRACE = timedelta(minutes=15)
INGEST_HARD_TIMEOUT = timedelta(minutes=40)


def _require_public_dashboard() -> None:
    if not get_settings().demo_public_dashboard:
        raise HTTPException(status_code=404, detail="Public dashboard disabled")


def _job_should_be_interrupted(
    job: JobRun,
    *,
    celery_state: str | None,
    now: datetime,
) -> bool:
    if job.status not in {JobRunStatus.queued, JobRunStatus.running}:
        return False
    anchor = job.started_at or job.created_at
    age = now - anchor
    if celery_state in {"FAILURE", "REVOKED"}:
        return True
    if age >= INGEST_HARD_TIMEOUT:
        return True
    if celery_state == "PENDING" and job.started_at and age >= INGEST_PENDING_GRACE:
        return True
    task_id = (job.result or {}).get("celery_task_id")
    return not task_id and age >= INGEST_LEGACY_GRACE


def _reconcile_public_ingest(db: Session, job: JobRun | None) -> JobRun | None:
    if job is None or job.status not in {JobRunStatus.queued, JobRunStatus.running}:
        return job
    task_id = (job.result or {}).get("celery_task_id")
    state = None
    async_result = None
    if task_id:
        try:
            from app.workers.celery_app import celery_app

            async_result = celery_app.AsyncResult(str(task_id))
            state = str(async_result.state)
        except Exception:  # noqa: BLE001
            state = None
    if state == "SUCCESS" and async_result is not None:
        result = async_result.result
        job.status = JobRunStatus.succeeded
        job.result = result if isinstance(result, dict) else {"celery_task_id": task_id}
        job.error_message = None
        job.finished_at = datetime.now(UTC)
        db.commit()
        return job
    now = datetime.now(UTC)
    if _job_should_be_interrupted(job, celery_state=state, now=now):
        job.status = JobRunStatus.failed
        job.error_message = "The update was interrupted and can be started again."
        job.finished_at = now
        db.commit()
    return job


@router.get("")
def get_dashboard(
    lookback_days: int = Query(default=5, ge=1, le=30),
    limit: int = Query(default=40, ge=1, le=600),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_public_dashboard()
    latest = db.scalar(
        select(JobRun)
        .where(JobRun.task_name == INGEST_TASK_NAME)
        .order_by(JobRun.created_at.desc())
        .limit(1)
    )
    _reconcile_public_ingest(db, latest)
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
    latest = _reconcile_public_ingest(db, latest)
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

        async_result = run_public_lookback_ingest.apply_async(
            args=[str(job.id), lookback_days, fetch_limit],
            queue=INGEST_QUEUE,
        )
        job.result = {"celery_task_id": async_result.id}
        db.commit()
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
