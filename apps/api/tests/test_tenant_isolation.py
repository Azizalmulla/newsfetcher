from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.db.seed import run_seed
from app.main import create_app


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
def test_cross_tenant_entity_isolation() -> None:
    run_seed()
    client = TestClient(create_app())

    suffix = uuid.uuid4().hex[:8]
    a = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Tenant A",
            "tenant_slug": f"tenant-a-{suffix}",
            "admin_email": f"admin-a-{suffix}@example.com",
            "admin_full_name": "Admin A",
            "password": "secure-password-a",
        },
    )
    assert a.status_code == 201, a.text
    token_a = a.json()["access_token"]

    b = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Tenant B",
            "tenant_slug": f"tenant-b-{suffix}",
            "admin_email": f"admin-b-{suffix}@example.com",
            "admin_full_name": "Admin B",
            "password": "secure-password-b",
        },
    )
    assert b.status_code == 201, b.text
    token_b = b.json()["access_token"]

    created = client.post(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "entity_type": "brand",
            "canonical_name_en": "AI Octopus",
            "canonical_name_ar": "إيه آي أوكتوبس",
            "aliases": [
                {"alias_text": "اي اي اوكتوبس", "language": "ar"},
                {"alias_text": "AI Octopus", "language": "en"},
            ],
            "exclusions": [{"phrase": "marine biology", "language": "en"}],
        },
    )
    assert created.status_code == 201, created.text
    entity_id = created.json()["id"]

    # Owner can read
    own = client.get(
        f"/api/v1/entities/{entity_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert own.status_code == 200
    assert own.json()["canonical_name_en"] == "AI Octopus"
    assert len(own.json()["aliases"]) == 2
    assert len(own.json()["exclusions"]) == 1

    # Other tenant must not see it (list or direct get)
    other_list = client.get(
        "/api/v1/entities",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert other_list.status_code == 200
    assert all(item["id"] != entity_id for item in other_list.json())

    other_get = client.get(
        f"/api/v1/entities/{entity_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert other_get.status_code == 404


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_login_and_me() -> None:
    run_seed()
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]
    slug = f"login-co-{suffix}"
    email = f"login-{suffix}@example.com"
    reg = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Login Co",
            "tenant_slug": slug,
            "admin_email": email,
            "admin_full_name": "Login Admin",
            "password": "secure-password-x",
        },
    )
    assert reg.status_code == 201
    login = client.post(
        "/api/v1/auth/login",
        json={
            "tenant_slug": slug,
            "email": email,
            "password": "secure-password-x",
        },
    )
    assert login.status_code == 200
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["tenant_slug"] == slug
