from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    phase: str


class ReadyResponse(BaseModel):
    status: str
    database: str
    redis: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name, phase="10")


@router.get("/ready", response_model=ReadyResponse)
def ready(db: Session = Depends(get_db)) -> ReadyResponse:
    database_status = "ok"
    redis_status = "ok"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        database_status = "error"

    try:
        import redis

        settings = get_settings()
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)
        client.ping()
    except Exception:
        redis_status = "error"

    status = "ok" if database_status == "ok" and redis_status == "ok" else "degraded"
    return ReadyResponse(status=status, database=database_status, redis=redis_status)
