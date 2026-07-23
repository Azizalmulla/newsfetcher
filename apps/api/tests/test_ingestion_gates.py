from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import run_seed
from app.models.enums import LegalGate
from app.models.sources import Publisher, SourceAssessment, SourceChannel, SourceConnectorConfig
from app.services.ingestion import channel_ingestion_allowed, discover_channel, normalize_url


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


def test_normalize_url_strips_query_and_slash() -> None:
    assert (
        normalize_url("HTTPS://Example.TEST/path/?utm=1")
        == "https://example.test/path"
    )


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_discovery_blocked_without_legal_gate() -> None:
    run_seed()
    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://newsfetcher:newsfetcher_dev_password@localhost:5433/newsfetcher",
    )
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    with SessionLocal() as db:
        publisher = db.scalar(select(Publisher).where(Publisher.code == "alanba"))
        assert publisher is not None
        channel = db.scalar(
            select(SourceChannel).where(
                SourceChannel.publisher_id == publisher.id,
                SourceChannel.code == "web_ar",
            )
        )
        assert channel is not None
        assessment = db.scalar(
            select(SourceAssessment).where(SourceAssessment.source_channel_id == channel.id)
        )
        connector = db.scalar(
            select(SourceConnectorConfig).where(
                SourceConnectorConfig.source_channel_id == channel.id
            )
        )
        assert assessment is not None and connector is not None
        assessment.legal_gate = LegalGate.pending
        connector.enabled = True
        db.commit()

        channel = db.scalar(
            select(SourceChannel)
            .where(SourceChannel.id == channel.id)
            .execution_options(populate_existing=True)
        )
        assert channel is not None
        # reload relationships
        db.refresh(assessment)
        db.refresh(connector)
        channel.assessment = assessment
        channel.connector_config = connector
        allowed, reason = channel_ingestion_allowed(channel, connector)
        assert allowed is False
        assert reason == "legal_gate_pending"

        result = discover_channel(db, channel.id)
        assert result["ok"] is False
        assert result["reason"] == "legal_gate_pending"
