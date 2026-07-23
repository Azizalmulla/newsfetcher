from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import run_seed
from app.main import create_app
from app.models.articles import Article
from app.models.semantic import SemanticCandidate
from app.models.sources import Publisher, SourceChannel


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
def test_semantic_pipeline_creates_explainable_candidates(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("RERANK_PROVIDER", "local")
    monkeypatch.setenv("EMBEDDING_FALLBACK_LOCAL", "true")
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    run_seed()
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]
    reg = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Semantic Co",
            "tenant_slug": f"semantic-co-{suffix}",
            "admin_email": f"semantic-{suffix}@example.com",
            "admin_full_name": "Semantic Admin",
            "password": "secure-password-s",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]

    entity = client.post(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "entity_type": "brand",
            "canonical_name_en": "AI Octopus",
            "canonical_name_ar": "إيه آي أوكتوبس",
            "semantic_instruction": "Monitor automation and AI contracts in Kuwait",
            "aliases": [{"alias_text": "اي اي اوكتوبس", "language": "ar"}],
            "exclusions": [{"phrase": "marine biology", "language": "en"}],
        },
    )
    assert entity.status_code == 201, entity.text

    url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://newsfetcher:newsfetcher_dev_password@localhost:5433/newsfetcher",
    )
    engine = create_engine(url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    with SessionLocal() as db:
        publisher = db.scalar(select(Publisher).limit(1))
        channel = db.scalar(
            select(SourceChannel).where(SourceChannel.publisher_id == publisher.id).limit(1)
        )
        assert publisher and channel
        related = Article(
            publisher_id=publisher.id,
            source_channel_id=channel.id,
            canonical_url=f"https://example.test/sem/{suffix}/related",
            source_url=f"https://example.test/sem/{suffix}/related",
            title="AI Octopus wins automation contract in Kuwait",
            language="en",
            body_original=(
                "AI Octopus signed a government automation agreement in Kuwait City this week."
            ),
            content_hash=f"rel-{suffix}",
            title_hash=f"rel-{suffix}",
            normalized_url=f"https://example.test/sem/{suffix}/related",
            discovered_at=datetime.now(UTC),
            metadata_={"fixture": "semantic_related"},
        )
        unrelated = Article(
            publisher_id=publisher.id,
            source_channel_id=channel.id,
            canonical_url=f"https://example.test/sem/{suffix}/unrelated",
            source_url=f"https://example.test/sem/{suffix}/unrelated",
            title="North Sea oil benchmark rises",
            language="en",
            body_original="Crude futures climbed after inventory draws in Europe.",
            content_hash=f"unrel-{suffix}",
            title_hash=f"unrel-{suffix}",
            normalized_url=f"https://example.test/sem/{suffix}/unrelated",
            discovered_at=datetime.now(UTC),
            metadata_={"fixture": "semantic_unrelated"},
        )
        db.add_all([related, unrelated])
        db.commit()
        related_id = related.id

    thresholds = client.put(
        "/api/v1/semantic/thresholds",
        headers={"Authorization": f"Bearer {token}"},
        json={"min_cosine": 0.40, "min_rerank": 0.05, "min_classifier": 0.50},
    )
    assert thresholds.status_code == 200, thresholds.text

    run = client.post(
        "/api/v1/semantic/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["ok"] is True
    assert body["provider"] == "local"
    assert body["candidates_created"] + body["candidates_updated"] >= 1

    candidates = client.get(
        "/api/v1/semantic/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert candidates.status_code == 200
    rows = candidates.json()
    assert rows
    assert all("vector_similarity" in row for row in rows)
    assert all("provenance" in row for row in rows)
    assert all(row["provenance"].get("embedding_provider") == "local" for row in rows)
    # Related article should be present; unexplained AI matches are forbidden.
    assert any(row["article_id"] == str(related_id) for row in rows)
    for row in rows:
        assert "embedding_model" in row["provenance"]
        assert "classifier" in row["provenance"]

    # Persist eval-style precision check against DB labels.
    with SessionLocal() as db:
        stored = db.scalars(
            select(SemanticCandidate).where(
                SemanticCandidate.tenant_id == uuid.UUID(reg.json()["tenant_id"])
            )
        ).all()
        assert stored
        assert any(item.article_id == related_id for item in stored)

    get_settings.cache_clear()
