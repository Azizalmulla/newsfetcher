from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.seed import run_seed
from app.main import create_app
from app.models.articles import Article, ArticleImage
from app.models.logos import LogoMatch
from app.models.sources import Publisher, SourceChannel
from app.services.logo_detection import (
    LocalCascadeLogoDetector,
    fingerprint_similarity,
    image_fingerprint,
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


def _png_bytes(tag: bytes) -> bytes:
    # Minimal valid-ish PNG header + payload for fingerprinting (not a real decoder path).
    return b"\x89PNG\r\n\x1a\n" + tag * 40


def test_local_cascade_screens_and_never_claims_final() -> None:
    template = _png_bytes(b"LOGO-A")
    same = template
    noise = _png_bytes(b"NOISE-ZZ")
    fp = image_fingerprint(template)
    assert fingerprint_similarity(fp, image_fingerprint(same)) == 1.0
    assert fingerprint_similarity(fp, image_fingerprint(noise)) < 0.35

    detector = LocalCascadeLogoDetector()
    hit = detector.detect(
        image_bytes=same,
        template_fingerprints=[("t1", fp, 0.72)],
    )
    assert hit.candidates
    assert hit.provider == "local"
    miss = detector.detect(
        image_bytes=noise,
        template_fingerprints=[("t1", fp, 0.72)],
    )
    assert miss.candidates == [] or all(c.confidence < 0.55 for c in miss.candidates)

    cases = json.loads(
        (Path(__file__).parent / "fixtures" / "logo_eval.json").read_text(encoding="utf-8")
    )
    assert all(case["expect_auto_included"] is False for case in cases["cases"])


@pytest.mark.skipif(not _db_available(), reason="PostgreSQL not available")
def test_logo_template_detect_review_report(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(storage_root))
    monkeypatch.setenv("LOGO_PROVIDER", "local")
    from app.core.config import get_settings

    get_settings.cache_clear()
    run_seed()
    client = TestClient(create_app())
    suffix = uuid.uuid4().hex[:8]

    reg = client.post(
        "/api/v1/auth/register-tenant",
        json={
            "tenant_name": "Logo Co",
            "tenant_slug": f"logo-co-{suffix}",
            "admin_email": f"logo-{suffix}@example.com",
            "admin_full_name": "Logo Admin",
            "password": "secure-password-l",
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
    entity_id = entity.json()["id"]

    logo_bytes = _png_bytes(b"OCTOPUS-MARK")
    upload = client.post(
        "/api/v1/logos/templates",
        headers=headers,
        data={
            "label": "AI Octopus mark",
            "variant": "primary",
            "track_role": "own",
            "entity_id": entity_id,
            "min_confidence": "0.50",
        },
        files={"file": ("logo.png", logo_bytes, "image/png")},
    )
    assert upload.status_code == 201, upload.text
    template = upload.json()
    assert template["feature_fingerprint"]

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
            canonical_url=f"https://example.test/logo/{suffix}",
            source_url=f"https://example.test/logo/{suffix}",
            title="Sponsored page",
            language="en",
            body_original="Photo page",
            content_hash=f"logo-{suffix}",
            title_hash=f"logo-{suffix}",
            normalized_url=f"https://example.test/logo/{suffix}",
            metadata_={},
        )
        db.add(article)
        db.flush()
        storage_key = f"tenants/test/article-images/{suffix}.png"
        (storage_root / storage_key).parent.mkdir(parents=True, exist_ok=True)
        (storage_root / storage_key).write_bytes(logo_bytes)
        image = ArticleImage(
            article_id=article.id,
            source_url=f"https://example.test/logo/{suffix}.png",
            storage_key=storage_key,
            metadata_={"fixture": "logo"},
        )
        db.add(image)
        db.commit()
        image_id = image.id

    detect = client.post(
        "/api/v1/logos/detect",
        headers=headers,
        json={"article_image_id": str(image_id)},
    )
    assert detect.status_code == 200, detect.text
    body = detect.json()
    assert body["auto_finalized"] is False
    assert body["matches_created"] >= 1

    matches = client.get("/api/v1/logos/matches", headers=headers, params={"status": "proposed"})
    assert matches.status_code == 200
    rows = matches.json()
    assert rows
    assert all(row["status"] == "proposed" for row in rows)
    match_id = rows[0]["id"]

    # Guard: DB must not contain auto-included rows from detect.
    with SessionLocal() as db:
        included = db.scalars(
            select(LogoMatch).where(
                LogoMatch.id == uuid.UUID(match_id), LogoMatch.status == "included"
            )
        ).all()
        assert included == []

    decide = client.post(
        f"/api/v1/logos/matches/{match_id}/decision",
        headers=headers,
        json={"status": "included", "note": "Confirmed logo crop", "bbox": {"x": 0.2, "y": 0.1}},
    )
    assert decide.status_code == 200, decide.text
    assert decide.json()["status"] == "included"

    draft = client.post(
        "/api/v1/reports",
        headers=headers,
        json={
            "title": f"Logo pack {suffix}",
            "include_included_cuttings": False,
            "include_included_logo_matches": True,
        },
    )
    assert draft.status_code == 201, draft.text
    assert any(item.get("logo_match_id") == match_id for item in draft.json()["items"])
