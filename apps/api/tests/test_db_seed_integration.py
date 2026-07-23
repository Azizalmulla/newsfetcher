from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import run_seed
from app.db.seed_data import expected_channel_count
from app.models.sources import Publisher, SourceAssessment, SourceChannel
from app.models.tenancy import Role


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


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_seed_creates_mandatory_inventory() -> None:
    run_seed()
    run_seed()  # idempotent

    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://newsfetcher:newsfetcher_dev_password@localhost:5433/newsfetcher",
    )
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    with SessionLocal() as db:
        publisher_count = db.scalar(select(func.count()).select_from(Publisher))
        channel_count = db.scalar(select(func.count()).select_from(SourceChannel))
        assessment_count = db.scalar(select(func.count()).select_from(SourceAssessment))
        roles = db.scalar(select(func.count()).select_from(Role))
        kuna = db.scalar(select(Publisher).where(Publisher.code == "kuna"))
        assert kuna is not None
        kuna_channels = db.scalars(
            select(SourceChannel).where(SourceChannel.publisher_id == kuna.id)
        ).all()

        assert publisher_count == 10
        assert channel_count == expected_channel_count()
        assert assessment_count == channel_count
        assert roles == 4
        assert {channel.language for channel in kuna_channels} == {"ar", "en"} or {
            getattr(channel.language, "value", channel.language) for channel in kuna_channels
        } == {"ar", "en"}
