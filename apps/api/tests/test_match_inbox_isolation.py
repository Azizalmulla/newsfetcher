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
def test_match_inbox_include_exclude_and_tenant_scope() -> None:
    run_seed()
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    reg = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Match Co",
            "tenant_slug": f"match-co-{suffix}",
            "admin_email": f"match-{suffix}@example.com",
            "admin_full_name": "Match Admin",
            "password": "secure-password-m",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant_id"]

    entity = client.post(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "entity_type": "brand",
            "canonical_name_en": "AI Octopus",
            "canonical_name_ar": "إيه آي أوكتوبس",
            "aliases": [{"alias_text": "اي اي اوكتوبس", "language": "ar"}],
            "exclusions": [{"phrase": "marine biology", "language": "en"}],
        },
    )
    assert entity.status_code == 201, entity.text

    # Insert an article directly for matching (ingestion may still be legally gated).
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
        article = Article(
            publisher_id=publisher.id,
            source_channel_id=channel.id,
            canonical_url=f"https://example.test/articles/{suffix}",
            source_url=f"https://example.test/articles/{suffix}",
            title="AI Octopus expands in Kuwait",
            language="en",
            body_original="AI Octopus announced a new automation project in Kuwait City.",
            body_normalized="ai octopus announced a new automation project in kuwait city",
            content_hash=suffix,
            title_hash=suffix,
            normalized_url=f"https://example.test/articles/{suffix}",
            discovered_at=datetime.now(UTC),
            metadata_={"fixture": True},
        )
        db.add(article)
        db.commit()
        article_id = str(article.id)

    run = client.post(
        "/api/v1/matches/run",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert run.status_code == 200, run.text
    assert run.json()["matches_created"] >= 1

    inbox = client.get(
        "/api/v1/matches/inbox",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert inbox.status_code == 200
    rows = inbox.json()
    assert len(rows) >= 1
    match_id = rows[0]["id"]
    assert rows[0]["status"] == "pending_review"
    assert rows[0]["evidence"]

    decided = client.post(
        f"/api/v1/matches/{match_id}/decision",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "included", "note": "Valid coverage"},
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "included"

    # Second tenant cannot see first tenant matches.
    other = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Other Co",
            "tenant_slug": f"other-co-{suffix}",
            "admin_email": f"other-{suffix}@example.com",
            "admin_full_name": "Other Admin",
            "password": "secure-password-o",
        },
    )
    assert other.status_code == 201
    other_inbox = client.get(
        "/api/v1/matches/inbox",
        headers={"Authorization": f"Bearer {other.json()['access_token']}"},
    )
    assert other_inbox.status_code == 200
    assert all(item["id"] != match_id for item in other_inbox.json())
    assert tenant_id
    assert article_id
