from __future__ import annotations

import os
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import run_seed
from app.main import create_app
from app.models.sources import Publisher, SourceChannel
from app.services.epaper import ingest_edition_pdf


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


def _make_pdf(text_lines: list[str]) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for line in text_lines:
        c.drawString(72, y, line)
        y -= 18
    c.showPage()
    c.save()
    return buffer.getvalue()


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_epaper_ingest_match_cutting_report(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(storage_root))
    monkeypatch.setenv("MISTRAL_API_KEY", "")
    monkeypatch.setenv("MISTRAL_OCR_MODEL", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    run_seed()
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    reg = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Epaper Co",
            "tenant_slug": f"epaper-co-{suffix}",
            "admin_email": f"epaper-{suffix}@example.com",
            "admin_full_name": "Epaper Admin",
            "password": "secure-password-e",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

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
        publisher = db.scalar(select(Publisher).where(Publisher.code == "alanba"))
        channel = db.scalar(
            select(SourceChannel).where(
                SourceChannel.publisher_id == publisher.id,
                SourceChannel.code == "epaper_ar",
            )
        )
        assert publisher and channel
        channel_id = channel.id

        # Legal gate still blocks gated upload path.
        blocked = False
        try:
            ingest_edition_pdf(
                db,
                channel_id=channel_id,
                edition_date=date(2026, 7, 22),
                pdf_bytes=_make_pdf(["blocked"]),
                actor_id=None,
                require_legal_gate=True,
            )
        except PermissionError as exc:
            blocked = str(exc) == "legal_gate_pending"
        assert blocked

        pdf_bytes = _make_pdf(
            [
                "Kuwait morning edition",
                "AI Octopus expands automation contracts in Kuwait City.",
                "Markets closed mixed.",
            ]
        )
        # Unique date per run avoids clobbering prior fixture editions.
        day = int(suffix[:2], 16) % 28 + 1
        edition = ingest_edition_pdf(
            db,
            channel_id=channel_id,
            edition_date=date(2026, 7, day),
            pdf_bytes=pdf_bytes,
            actor_id=None,
            title=f"Alanba fixture {suffix}",
            require_legal_gate=False,
            ingest_mode="upload_fixture",
        )
        edition_id = edition.id
        assert edition.status == "ocr_done"
        assert edition.page_count == 1
        assert edition.pdf_sha256
        assert edition.pages[0].blocks
        assert "AI Octopus" in (edition.pages[0].full_text or "")

    match = client.post(f"/api/v1/epaper/editions/{edition_id}/match", headers=headers)
    assert match.status_code == 200, match.text
    assert match.json()["cuttings_created"] >= 1

    cuttings = client.get(
        "/api/v1/epaper/cuttings",
        headers=headers,
        params={"edition_id": str(edition_id)},
    )
    assert cuttings.status_code == 200
    rows = cuttings.json()
    assert len(rows) >= 1
    cutting_id = rows[0]["id"]

    adjust = client.post(
        f"/api/v1/epaper/cuttings/{cutting_id}/decision",
        headers=headers,
        json={
            "status": "included",
            "note": "Keep for pack",
            "bbox": {"x": 0.1, "y": 0.2, "w": 0.8, "h": 0.15},
        },
    )
    assert adjust.status_code == 200, adjust.text
    assert adjust.json()["status"] == "included"

    draft = client.post(
        "/api/v1/reports",
        headers=headers,
        json={
            "title": f"Epaper pack {suffix}",
            "include_included_cuttings": True,
        },
    )
    assert draft.status_code == 201, draft.text
    items = draft.json()["items"]
    assert any(item.get("cutting_id") == cutting_id for item in items)


def test_text_layer_extraction_and_weak_page_ocr_fallback() -> None:
    from app.services.ocr import resolve_page_ocr
    from app.services.pdf_text import extract_text_layer, text_layer_is_weak

    rich = _make_pdf(["AI Octopus headline", "Body paragraph with enough characters here."])
    pages = extract_text_layer(rich)
    assert len(pages) == 1
    assert not text_layer_is_weak(pages[0])
    result = resolve_page_ocr(pages[0], pdf_bytes=rich)
    assert result.provider == "text_layer"

    # Nearly empty page forces local OCR stub when Mistral is unset.
    sparse = _make_pdf(["x"])
    sparse_pages = extract_text_layer(sparse)
    assert text_layer_is_weak(sparse_pages[0])
    stub = resolve_page_ocr(sparse_pages[0], pdf_bytes=sparse)
    assert stub.provider in {"local_stub", "text_layer"}
