from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    dashboard,
    entities,
    epaper,
    health,
    ingestion,
    logos,
    matches,
    reports,
    semantic,
    social,
    sources,
)
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.observability import init_otel, init_sentry


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="NewsFetcher API",
        version="0.10.0",
        description="Kuwait media-monitoring SaaS",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_sentry(settings)
    init_otel(app, settings)

    app.include_router(health.router)
    app.include_router(dashboard.router, prefix="/api/v1")
    app.include_router(sources.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(entities.router, prefix="/api/v1")
    app.include_router(ingestion.router, prefix="/api/v1")
    app.include_router(matches.router, prefix="/api/v1")
    app.include_router(semantic.router, prefix="/api/v1")
    app.include_router(reports.router, prefix="/api/v1")
    app.include_router(epaper.router, prefix="/api/v1")
    app.include_router(logos.router, prefix="/api/v1")
    app.include_router(social.router, prefix="/api/v1")

    return app


app = create_app()
