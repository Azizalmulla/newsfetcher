from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from newsfetcher_connectors.registry import get_connector, list_connector_types
from newsfetcher_connectors.types import ConnectorContext, ConnectorType
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, selectinload, sessionmaker

from app.db.seed import run_seed
from app.db.seed_data import expected_channel_count
from app.main import create_app
from app.models.enums import LegalGate
from app.models.sources import SourceAssessment, SourceChannel, SourceConnectorConfig
from app.services.source_closure import (
    apply_source_closure,
    list_source_closure,
    matrix_covers_all_seed_channels,
)


def _db_available() -> bool:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://newsfetcher:newsfetcher_dev_password@localhost:5433/newsfetcher",
    )
    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def test_matrix_covers_every_seed_channel() -> None:
    ok, problems = matrix_covers_all_seed_channels()
    assert ok, problems


def test_phase8_gated_connectors_registered_and_inert_by_default() -> None:
    types = set(list_connector_types())
    assert {"browser", "licensed_api", "epaper", "html", "sitemap", "rss"} <= types
    for ctype in (ConnectorType.browser, ConnectorType.licensed_api, ConnectorType.epaper):
        result = get_connector(ctype).discover(
            ConnectorContext(
                publisher_code="alanba",
                channel_code="epaper_ar",
                base_url="https://www.alanba.com.kw",
                language="ar",
                config={"requires_license": True},  # browser_enabled omitted → no launch
            )
        )
        assert result.items == []
        assert result.errors


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_apply_closure_closes_all_channels_without_enabling() -> None:
    run_seed()
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://newsfetcher:newsfetcher_dev_password@localhost:5433/newsfetcher",
    )
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    with SessionLocal() as db:
        result = apply_source_closure(db, actor_id="test")
        assert result["applied"] == expected_channel_count()
        assert result["enabled_connectors"] == 0
        assert result["missing"] == []

        closure = list_source_closure(db)
        assert closure["phase8_complete"] is True
        assert closure["open_count"] == 0
        assert closure["enabled_connectors"] == 0
        assert closure["disposition_counts"]["active"] >= 1
        # awaiting_licensing may be 0 once public e-paper is classified active.

        enabled = db.scalars(
            select(SourceConnectorConfig).where(SourceConnectorConfig.enabled.is_(True))
        ).all()
        assert enabled == []

        approved = db.scalars(
            select(SourceAssessment).where(SourceAssessment.legal_gate == LegalGate.approved)
        ).all()
        assert approved == []

        epaper = db.scalar(
            select(SourceChannel)
            .where(SourceChannel.code == "epaper_ar")
            .options(selectinload(SourceChannel.assessment), selectinload(SourceChannel.connector_config))
        )
        assert epaper is not None
        assert epaper.assessment is not None
        assert epaper.assessment.phase8_disposition == "active"
        assert epaper.connector_config is not None
        assert epaper.connector_config.enabled is False
        assert epaper.assessment.legal_gate == LegalGate.pending


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_closure_api_and_seed_idempotent() -> None:
    run_seed()
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]
    reg = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Closure Co",
            "tenant_slug": f"closure-co-{suffix}",
            "admin_email": f"closure-{suffix}@example.com",
            "admin_full_name": "Closure Admin",
            "password": "secure-password-c",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    dashboard = client.get("/api/v1/sources/closure", headers=headers)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["phase8_complete"] is True
    assert body["enabled_connectors"] == 0

    applied = client.post("/api/v1/sources/closure/apply", headers=headers)
    assert applied.status_code == 200, applied.text
    assert applied.json()["enabled_connectors"] == 0
    assert applied.json()["legal_gates_approved"] == 0
