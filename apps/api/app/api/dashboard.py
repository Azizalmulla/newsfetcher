"""Public no-auth dashboard endpoints for the live demo UI."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.services.dashboard import build_dashboard
from app.services.ingestion_pipeline import run_lookback_ingest

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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


def _run_ingest_job(*, lookback_days: int, fetch_limit: int) -> None:
    db = SessionLocal()
    try:
        run_lookback_ingest(
            db,
            lookback_days=lookback_days,
            fetch_limit=fetch_limit,
            actor_id="public-demo",
            include_temporarily_broken=True,
            enable_first=True,
            use_browser_fallback=True,
        )
    finally:
        db.close()


@router.post("/ingest")
def trigger_public_ingest(
    background_tasks: BackgroundTasks,
    lookback_days: int = Query(default=5, ge=1, le=14),
    fetch_limit: int = Query(default=400, ge=50, le=1200),
) -> dict[str, Any]:
    _require_public_dashboard()
    if not get_settings().demo_public_ingest:
        raise HTTPException(status_code=403, detail="Public ingest disabled")
    background_tasks.add_task(
        _run_ingest_job, lookback_days=lookback_days, fetch_limit=fetch_limit
    )
    return {
        "status": "started",
        "lookback_days": lookback_days,
        "fetch_limit": fetch_limit,
        "message": "Ingest started in the background. Refresh the dashboard in a few minutes.",
    }
