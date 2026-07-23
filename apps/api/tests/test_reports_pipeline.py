from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

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
def test_report_draft_reorder_approve_deliver_archive(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    storage_root = tmp_path / "storage"
    mail_root = tmp_path / "mail"
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(storage_root))
    monkeypatch.setenv("EMAIL_BACKEND", "file")
    monkeypatch.setenv("EMAIL_FILE_DIR", str(mail_root))
    from app.core.config import get_settings

    get_settings.cache_clear()

    run_seed()
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    reg = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Report Co",
            "tenant_slug": f"report-co-{suffix}",
            "admin_email": f"report-{suffix}@example.com",
            "admin_full_name": "Report Admin",
            "password": "secure-password-r",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    branding = client.put(
        "/api/v1/reports/branding",
        headers=headers,
        json={
            "display_name": "Report Co Kuwait",
            "primary_color": "#0B3D2E",
            "accent_color": "#C4A35A",
            "footer_text": "Private clipping pack",
        },
    )
    assert branding.status_code == 200, branding.text

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
        for idx in range(2):
            db.add(
                Article(
                    publisher_id=publisher.id,
                    source_channel_id=channel.id,
                    canonical_url=f"https://example.test/report/{suffix}/{idx}",
                    source_url=f"https://example.test/report/{suffix}/{idx}",
                    title=f"AI Octopus story {idx}",
                    language="en",
                    body_original=f"AI Octopus announced project {idx} in Kuwait.",
                    content_hash=f"rep-{suffix}-{idx}",
                    title_hash=f"rep-{suffix}-{idx}",
                    normalized_url=f"https://example.test/report/{suffix}/{idx}",
                    discovered_at=datetime.now(UTC),
                    metadata_={"fixture": "report"},
                )
            )
        db.commit()

    run = client.post("/api/v1/matches/run", headers=headers)
    assert run.status_code == 200, run.text

    inbox = client.get(
        "/api/v1/matches/inbox",
        headers=headers,
        params={"status": "pending_review"},
    )
    assert inbox.status_code == 200
    matches = inbox.json()
    assert len(matches) >= 2
    for match in matches[:2]:
        decide = client.post(
            f"/api/v1/matches/{match['id']}/decision",
            headers=headers,
            json={"status": "included", "note": "keep"},
        )
        assert decide.status_code == 200, decide.text

    draft = client.post(
        "/api/v1/reports",
        headers=headers,
        json={
            "title": f"Weekly clipping {suffix}",
            "period_start": date(2026, 7, 14).isoformat(),
            "period_end": date(2026, 7, 21).isoformat(),
            "notes": "Draft for client review",
        },
    )
    assert draft.status_code == 201, draft.text
    report = draft.json()
    assert report["status"] == "draft"
    assert len(report["items"]) >= 2
    report_id = report["id"]
    item_ids = [item["id"] for item in report["items"]]

    # Annotate + exclude one item, then reorder.
    note = client.patch(
        f"/api/v1/reports/{report_id}/items/{item_ids[0]}",
        headers=headers,
        json={"note": "Lead story", "included": True},
    )
    assert note.status_code == 200, note.text
    exclude = client.patch(
        f"/api/v1/reports/{report_id}/items/{item_ids[1]}",
        headers=headers,
        json={"included": False, "note": "Hold for next week"},
    )
    assert exclude.status_code == 200, exclude.text

    reordered = list(reversed(item_ids))
    reorder = client.put(
        f"/api/v1/reports/{report_id}/items/reorder",
        headers=headers,
        json={"ordered_item_ids": reordered},
    )
    assert reorder.status_code == 200, reorder.text
    assert [item["id"] for item in reorder.json()["items"]] == reordered

    review = client.patch(
        f"/api/v1/reports/{report_id}",
        headers=headers,
        json={"status": "in_review", "notes": "Ready for approval"},
    )
    assert review.status_code == 200
    assert review.json()["status"] == "in_review"

    approve = client.post(f"/api/v1/reports/{report_id}/approve", headers=headers)
    assert approve.status_code == 200, approve.text
    final = approve.json()
    assert final["status"] == "final"
    assert len(final["versions"]) == 1
    version = final["versions"][0]
    assert version["pdf_sha256"]
    assert version["content_hash"]
    assert (storage_root / version["pdf_storage_key"]).is_file()

    # Immutable after approve.
    blocked = client.patch(
        f"/api/v1/reports/{report_id}",
        headers=headers,
        json={"notes": "should fail"},
    )
    assert blocked.status_code == 409

    pdf = client.get(f"/api/v1/reports/{report_id}/versions/1/pdf", headers=headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"

    deliver = client.post(
        f"/api/v1/reports/{report_id}/versions/1/deliver",
        headers=headers,
        json={"recipients": [f"client-{suffix}@example.com"]},
    )
    assert deliver.status_code == 200, deliver.text
    assert deliver.json()["email_status"] == "sent"
    assert list(mail_root.glob("*.eml")) or list(mail_root.glob("*.pdf"))

    archive = client.post(f"/api/v1/reports/{report_id}/archive", headers=headers)
    assert archive.status_code == 200
    assert archive.json()["status"] == "archived"

    revise = client.post(f"/api/v1/reports/{report_id}/revise", headers=headers)
    assert revise.status_code == 201, revise.text
    assert revise.json()["status"] == "draft"
    assert revise.json()["id"] != report_id
