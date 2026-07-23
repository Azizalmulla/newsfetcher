from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, require_roles
from app.db.session import get_db
from app.models.sources import Publisher, SourceChannel
from app.services.article_fetch import fetch_article_bodies
from app.services.ingestion import discover_channel
from app.services.ingestion_pipeline import (
    article_stats,
    discover_all_enabled,
    run_lookback_ingest,
)
from app.services.source_enablement import enable_web_sources

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/discover/{publisher_code}/{channel_code}")
def trigger_discovery(
    publisher_code: str,
    channel_code: str,
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Attempt discovery. Blocked unless legal_gate approved and connector enabled."""
    _ = auth
    publisher = db.scalar(select(Publisher).where(Publisher.code == publisher_code))
    if publisher is None:
        raise HTTPException(status_code=404, detail="publisher not found")
    channel = db.scalar(
        select(SourceChannel).where(
            SourceChannel.publisher_id == publisher.id,
            SourceChannel.code == channel_code,
        )
    )
    if channel is None:
        raise HTTPException(status_code=404, detail="channel not found")
    return discover_channel(db, channel.id)


@router.post("/discover-by-id/{channel_id}")
def trigger_discovery_by_id(
    channel_id: UUID,
    auth: AuthContext = Depends(require_roles("platform_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = auth
    return discover_channel(db, channel_id)


@router.post("/enable-web-sources")
def enable_sources(
    lookback_days: int = Query(default=5, ge=1, le=30),
    include_temporarily_broken: bool = Query(default=True),
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Explicit ops approval: legal_gate=approved + connectors enabled for web sources."""
    return enable_web_sources(
        db,
        lookback_days=lookback_days,
        actor_id=str(auth.user.id),
        include_temporarily_broken=include_temporarily_broken,
    )


@router.post("/discover-all")
def discover_all(
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = auth
    return discover_all_enabled(db)


@router.post("/fetch-bodies")
def fetch_bodies(
    lookback_days: int = Query(default=5, ge=1, le=30),
    limit: int = Query(default=400, ge=1, le=2000),
    use_browser_fallback: bool = Query(default=True),
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = auth
    return fetch_article_bodies(
        db,
        lookback_days=lookback_days,
        limit=limit,
        use_browser_fallback=use_browser_fallback,
    )


@router.post("/run-lookback")
def run_lookback(
    lookback_days: int = Query(default=5, ge=1, le=30),
    fetch_limit: int = Query(default=800, ge=1, le=2000),
    include_temporarily_broken: bool = Query(default=True),
    use_browser_fallback: bool = Query(default=True),
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Enable web sources, discover, and fetch bodies for the lookback window."""
    return run_lookback_ingest(
        db,
        lookback_days=lookback_days,
        fetch_limit=fetch_limit,
        actor_id=str(auth.user.id),
        include_temporarily_broken=include_temporarily_broken,
        enable_first=True,
        use_browser_fallback=use_browser_fallback,
    )


@router.get("/article-stats")
def get_article_stats(
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = auth
    return article_stats(db)


# Back-compat aliases for earlier demo endpoints.
@router.post("/demo/enable-web-sources")
def demo_enable_web_sources(
    lookback_days: int = Query(default=5, ge=1, le=30),
    include_temporarily_broken: bool = Query(default=True),
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return enable_web_sources(
        db,
        lookback_days=lookback_days,
        actor_id=str(auth.user.id),
        include_temporarily_broken=include_temporarily_broken,
    )


@router.post("/demo/discover-all")
def demo_discover_all(
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = auth
    return discover_all_enabled(db)


@router.post("/demo/fetch-bodies")
def demo_fetch_bodies(
    lookback_days: int = Query(default=5, ge=1, le=30),
    limit: int = Query(default=400, ge=1, le=2000),
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = auth
    return fetch_article_bodies(
        db, lookback_days=lookback_days, limit=limit, use_browser_fallback=True
    )


@router.post("/demo/scrape-lookback")
def demo_scrape_lookback(
    lookback_days: int = Query(default=5, ge=1, le=30),
    fetch_limit: int = Query(default=800, ge=1, le=2000),
    include_temporarily_broken: bool = Query(default=True),
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return run_lookback_ingest(
        db,
        lookback_days=lookback_days,
        fetch_limit=fetch_limit,
        actor_id=str(auth.user.id),
        include_temporarily_broken=include_temporarily_broken,
        enable_first=True,
        use_browser_fallback=True,
    )


@router.get("/demo/article-stats")
def demo_article_stats(
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _ = auth
    return article_stats(db)
