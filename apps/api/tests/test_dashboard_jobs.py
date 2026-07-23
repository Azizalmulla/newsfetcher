from datetime import UTC, datetime, timedelta

from app.api.dashboard import _job_should_be_interrupted
from app.models.enums import JobRunStatus
from app.models.observability import JobRun


def _job(
    *,
    status: JobRunStatus = JobRunStatus.running,
    age_minutes: int,
    started: bool = True,
    task_id: str | None = "task-1",
) -> tuple[JobRun, datetime]:
    now = datetime.now(UTC)
    created_at = now - timedelta(minutes=age_minutes)
    return (
        JobRun(
            queue_name="source.discovery",
            task_name="ingestion.lookback.public",
            status=status,
            payload={},
            result={"celery_task_id": task_id} if task_id else {},
            created_at=created_at,
            started_at=created_at if started else None,
        ),
        now,
    )


def test_legacy_job_without_task_id_is_recovered() -> None:
    job, now = _job(age_minutes=16, task_id=None)
    assert _job_should_be_interrupted(job, celery_state=None, now=now)


def test_recent_active_job_is_not_interrupted() -> None:
    job, now = _job(age_minutes=10)
    assert not _job_should_be_interrupted(job, celery_state="STARTED", now=now)


def test_lost_started_job_is_recovered_after_pending_grace() -> None:
    job, now = _job(age_minutes=6)
    assert _job_should_be_interrupted(job, celery_state="PENDING", now=now)


def test_any_active_job_is_recovered_after_hard_timeout() -> None:
    job, now = _job(age_minutes=41)
    assert _job_should_be_interrupted(job, celery_state="STARTED", now=now)


def test_terminal_job_is_never_reconciled() -> None:
    job, now = _job(status=JobRunStatus.succeeded, age_minutes=90)
    assert not _job_should_be_interrupted(job, celery_state="SUCCESS", now=now)
