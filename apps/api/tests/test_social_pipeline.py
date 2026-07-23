from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.core.config import Settings
from app.db.seed import run_seed
from app.main import create_app
from app.services.x_api import GatedXApiClient


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


def test_gated_x_client_refuses_without_gates() -> None:
    settings = Settings(x_api_live_enabled=True, x_api_bearer_token="tok")
    client = GatedXApiClient(settings, gates_ok=False)
    with pytest.raises(PermissionError, match="gates_incomplete"):
        client.fetch_user_timeline(handle="KUNAonline")


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_social_fixture_match_review_and_poll_blocked() -> None:
    run_seed()
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]
    reg = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Social Co",
            "tenant_slug": f"social-co-{suffix}",
            "admin_email": f"social-{suffix}@example.com",
            "admin_full_name": "Social Admin",
            "password": "secure-password-s",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    gate = client.get("/api/v1/social/x/gate", headers=headers)
    assert gate.status_code == 200
    assert gate.json()["live_ready"] is False
    assert gate.json()["scrape_forbidden"] is True

    # Cannot enable live before checklist.
    blocked_enable = client.put(
        "/api/v1/social/x/gate",
        headers=headers,
        json={"live_enabled": True},
    )
    assert blocked_enable.status_code == 400

    accounts = client.get("/api/v1/social/accounts", headers=headers)
    assert accounts.status_code == 200
    rows = accounts.json()
    assert len(rows) >= 4
    account_id = next(row["id"] for row in rows if row["handle"] == "KUNAonline")

    approve = client.post(
        f"/api/v1/social/accounts/{account_id}/approval",
        headers=headers,
        json={"approved": True},
    )
    assert approve.status_code == 200
    assert approve.json()["is_approved"] is True

    poll = client.post("/api/v1/social/poll", headers=headers)
    assert poll.status_code == 200
    assert poll.json()["ok"] is False
    assert poll.json()["reason"] == "gates_incomplete"

    entity = client.post(
        "/api/v1/entities",
        headers=headers,
        json={
            "entity_type": "brand",
            "canonical_name_en": "AI Octopus",
            "canonical_name_ar": "إيه آي أوكتوبس",
        },
    )
    assert entity.status_code == 201, entity.text

    fixture = client.post(
        "/api/v1/social/fixture-ingest",
        headers=headers,
        json={
            "handle": "KUNAonline",
            "posts": [
                {
                    "text": "AI Octopus signs Kuwait digital services MoU.",
                    "external_post_id": f"fx-{suffix}",
                }
            ],
        },
    )
    assert fixture.status_code == 200, fixture.text
    assert fixture.json()["posts_created"] == 1
    assert fixture.json()["ingest_source"] == "fixture"

    matched = client.post("/api/v1/social/match", headers=headers)
    assert matched.status_code == 200, matched.text
    assert matched.json()["matches_created"] >= 1
    assert matched.json()["auto_finalized"] is False

    inbox = client.get("/api/v1/social/matches", headers=headers, params={"status": "proposed"})
    assert inbox.status_code == 200
    assert inbox.json()
    match_id = inbox.json()[0]["id"]

    decide = client.post(
        f"/api/v1/social/matches/{match_id}/decision",
        headers=headers,
        json={"status": "included", "note": "Keep for pack"},
    )
    assert decide.status_code == 200
    assert decide.json()["status"] == "included"

    draft = client.post(
        "/api/v1/reports",
        headers=headers,
        json={
            "title": f"Social pack {suffix}",
            "include_included_cuttings": False,
            "include_included_logo_matches": False,
            "include_included_social_matches": True,
        },
    )
    assert draft.status_code == 201, draft.text
    assert any(item.get("social_match_id") == match_id for item in draft.json()["items"])
