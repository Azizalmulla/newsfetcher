from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models.monitoring import MonitoringEntity
from app.models.social import SocialAccount, SocialIntegrationGate, SocialMatch, SocialPost
from app.models.sources import Publisher
from app.services.audit import write_audit
from app.services.matching import entity_terms
from app.services.matching_engine import match_document
from app.services.x_api import XPostPayload, build_x_client, sample_fixture_post

# Approved-outlet shortlist (handles only). is_approved starts false until ops review.
OUTLET_SEED: list[dict[str, str]] = [
    {"handle": "KUNAonline", "display_name": "KUNA", "publisher_code": "kuna"},
    {"handle": "alanba_news", "display_name": "Al-Anbaa", "publisher_code": "alanba"},
    {"handle": "alqabas", "display_name": "Al Qabas", "publisher_code": "alqabas"},
    {"handle": "KuwaitTimes", "display_name": "Kuwait Times", "publisher_code": "kuwaittimes"},
]


def get_or_create_x_gate(db: Session) -> SocialIntegrationGate:
    gate = db.scalar(select(SocialIntegrationGate).where(SocialIntegrationGate.platform == "x"))
    if gate is None:
        gate = SocialIntegrationGate(
            id=uuid4(),
            platform="x",
            checklist={
                "doc": "docs/sources/SOCIAL_X_TERMS_COST_CHECKLIST.md",
                "scrape_forbidden": True,
            },
            notes="Phase 10 default: live X polling disabled until checklist complete.",
        )
        db.add(gate)
        db.commit()
        db.refresh(gate)
    return gate


def gates_allow_live(db: Session) -> tuple[bool, list[str]]:
    settings = get_settings()
    gate = get_or_create_x_gate(db)
    missing: list[str] = []
    if not gate.credentials_available and not settings.x_api_bearer_token:
        missing.append("credentials")
    if not gate.pricing_reviewed:
        missing.append("pricing_reviewed")
    if not gate.endpoints_confirmed:
        missing.append("endpoints_confirmed")
    if not gate.terms_documented:
        missing.append("terms_documented")
    if not gate.cost_approved:
        missing.append("cost_approved")
    if not gate.live_enabled:
        missing.append("live_enabled")
    if not settings.x_api_live_enabled:
        missing.append("X_API_LIVE_ENABLED")
    if not settings.x_api_bearer_token:
        missing.append("X_API_BEARER_TOKEN")
    return (len(missing) == 0), missing


def update_x_gate(
    db: Session,
    *,
    actor_id: str | None,
    credentials_available: bool | None = None,
    pricing_reviewed: bool | None = None,
    endpoints_confirmed: bool | None = None,
    terms_documented: bool | None = None,
    cost_approved: bool | None = None,
    live_enabled: bool | None = None,
    notes: str | None = None,
) -> SocialIntegrationGate:
    gate = get_or_create_x_gate(db)
    if credentials_available is not None:
        gate.credentials_available = credentials_available
    if pricing_reviewed is not None:
        gate.pricing_reviewed = pricing_reviewed
    if endpoints_confirmed is not None:
        gate.endpoints_confirmed = endpoints_confirmed
    if terms_documented is not None:
        gate.terms_documented = terms_documented
    if cost_approved is not None:
        gate.cost_approved = cost_approved
    if live_enabled is not None:
        # Refuse live_enabled unless other flags are already true.
        if live_enabled:
            ok_flags = all(
                [
                    gate.credentials_available or bool(get_settings().x_api_bearer_token),
                    gate.pricing_reviewed,
                    gate.endpoints_confirmed,
                    gate.terms_documented,
                    gate.cost_approved,
                ]
            )
            if not ok_flags:
                raise ValueError("Cannot enable live X polling before checklist flags are complete")
        gate.live_enabled = live_enabled
    if notes is not None:
        gate.notes = notes
    write_audit(
        db,
        tenant_id=None,
        actor_id=actor_id,
        action="social.x_gate_updated",
        resource_type="social_integration_gate",
        resource_id=str(gate.id),
        details={
            "live_enabled": gate.live_enabled,
            "cost_approved": gate.cost_approved,
            "terms_documented": gate.terms_documented,
        },
    )
    db.commit()
    db.refresh(gate)
    return gate


def seed_outlet_accounts(db: Session) -> int:
    created = 0
    for row in OUTLET_SEED:
        existing = db.scalar(
            select(SocialAccount).where(
                SocialAccount.platform == "x",
                SocialAccount.handle == row["handle"],
            )
        )
        if existing:
            continue
        publisher = db.scalar(select(Publisher).where(Publisher.code == row["publisher_code"]))
        db.add(
            SocialAccount(
                id=uuid4(),
                platform="x",
                handle=row["handle"],
                display_name=row["display_name"],
                publisher_id=publisher.id if publisher else None,
                account_type="outlet",
                is_approved=False,
                is_active=True,
                metadata_={"seed": "phase10", "awaiting_ops_approval": True},
            )
        )
        created += 1
    get_or_create_x_gate(db)
    db.commit()
    return created


def list_accounts(db: Session, *, approved_only: bool = False) -> list[SocialAccount]:
    stmt = select(SocialAccount).where(SocialAccount.platform == "x").order_by(SocialAccount.handle)
    if approved_only:
        stmt = stmt.where(SocialAccount.is_approved.is_(True), SocialAccount.is_active.is_(True))
    return list(db.scalars(stmt).all())


def set_account_approval(
    db: Session, *, account_id: UUID, actor_id: str, approved: bool
) -> SocialAccount:
    account = db.get(SocialAccount, account_id)
    if account is None:
        raise KeyError("Social account not found")
    account.is_approved = approved
    write_audit(
        db,
        tenant_id=None,
        actor_id=actor_id,
        action="social.account_approval",
        resource_type="social_account",
        resource_id=str(account.id),
        details={"approved": approved, "handle": account.handle},
    )
    db.commit()
    db.refresh(account)
    return account


def _upsert_posts(
    db: Session,
    *,
    account: SocialAccount,
    payloads: list[XPostPayload],
    ingest_source: str,
) -> int:
    created = 0
    for payload in payloads:
        existing = db.scalar(
            select(SocialPost).where(
                SocialPost.platform == "x",
                SocialPost.external_post_id == payload.external_post_id,
            )
        )
        if existing:
            continue
        db.add(
            SocialPost(
                id=uuid4(),
                platform="x",
                account_id=account.id,
                external_post_id=payload.external_post_id,
                posted_at=payload.posted_at,
                language=payload.language,
                text=payload.text,
                permalink=payload.permalink,
                ingest_source=ingest_source,
                raw=payload.raw,
            )
        )
        created += 1
    db.commit()
    return created


def ingest_fixture_posts(
    db: Session,
    *,
    handle: str,
    posts: list[dict[str, str]],
    actor_id: str | None = None,
) -> dict[str, object]:
    account = db.scalar(
        select(SocialAccount).where(
            SocialAccount.platform == "x",
            SocialAccount.handle == handle.lstrip("@"),
        )
    )
    if account is None:
        raise KeyError("Social account not found")
    payloads = [
        sample_fixture_post(
            handle=account.handle,
            text=row["text"],
            external_id=row.get("external_post_id") or f"fixture-{uuid4().hex[:12]}",
        )
        for row in posts
    ]
    created = _upsert_posts(db, account=account, payloads=payloads, ingest_source="fixture")
    write_audit(
        db,
        tenant_id=None,
        actor_id=actor_id,
        action="social.fixture_ingested",
        resource_type="social_account",
        resource_id=str(account.id),
        details={"created": created},
    )
    return {"handle": account.handle, "posts_created": created, "ingest_source": "fixture"}


def poll_approved_accounts(db: Session, *, actor_id: str | None = None) -> dict[str, object]:
    ok, missing = gates_allow_live(db)
    if not ok:
        return {
            "ok": False,
            "reason": "gates_incomplete",
            "missing": missing,
            "polled": 0,
            "posts_created": 0,
        }
    accounts = list_accounts(db, approved_only=True)
    if not accounts:
        return {
            "ok": False,
            "reason": "no_approved_accounts",
            "missing": [],
            "polled": 0,
            "posts_created": 0,
        }
    client = build_x_client(gates_ok=True)
    total = 0
    for account in accounts:
        payloads = client.fetch_user_timeline(handle=account.handle, max_results=10)
        total += _upsert_posts(
            db, account=account, payloads=payloads, ingest_source="official_api"
        )
    write_audit(
        db,
        tenant_id=None,
        actor_id=actor_id,
        action="social.polled_official_api",
        resource_type="social",
        resource_id="x",
        details={"accounts": len(accounts), "posts_created": total},
    )
    return {
        "ok": True,
        "reason": "ok",
        "missing": [],
        "polled": len(accounts),
        "posts_created": total,
        "ingest_source": "official_api",
    }


def match_posts_for_tenant(db: Session, *, tenant_id: UUID) -> dict[str, object]:
    entities = db.scalars(
        select(MonitoringEntity)
        .where(
            MonitoringEntity.tenant_id == tenant_id,
            MonitoringEntity.is_active.is_(True),
        )
        .options(
            selectinload(MonitoringEntity.aliases),
            selectinload(MonitoringEntity.exclusions),
        )
    ).all()
    posts = db.scalars(select(SocialPost).order_by(SocialPost.created_at.desc()).limit(500)).all()
    created = 0
    updated = 0
    for post in posts:
        for entity in entities:
            terms = [term for term in entity_terms(entity) if term.surface]
            if not terms:
                continue
            exclusions = [row.phrase_normalized for row in entity.exclusions]
            candidate = match_document(
                title=None,
                body=post.text,
                terms=terms,
                exclusions_normalized=exclusions,
            )
            if candidate is None or candidate.excluded:
                continue
            existing = db.scalar(
                select(SocialMatch).where(
                    SocialMatch.tenant_id == tenant_id,
                    SocialMatch.entity_id == entity.id,
                    SocialMatch.post_id == post.id,
                )
            )
            evidence = {
                "hits": [
                    {
                        "match_type": hit.match_type,
                        "score": hit.score,
                        "span": hit.evidence_span,
                    }
                    for hit in candidate.evidence
                ],
                "auto_finalized": False,
                "platform": post.platform,
            }
            if existing is None:
                db.add(
                    SocialMatch(
                        id=uuid4(),
                        tenant_id=tenant_id,
                        entity_id=entity.id,
                        post_id=post.id,
                        status="proposed",
                        best_match_type=candidate.best_match_type,
                        best_score=candidate.best_score,
                        matched_term=candidate.matched_term,
                        snippet=candidate.snippet,
                        evidence=evidence,
                    )
                )
                created += 1
            elif existing.status == "proposed":
                existing.best_match_type = candidate.best_match_type
                existing.best_score = candidate.best_score
                existing.matched_term = candidate.matched_term
                existing.snippet = candidate.snippet
                existing.evidence = evidence
                updated += 1
    db.commit()
    return {
        "matches_created": created,
        "matches_updated": updated,
        "posts_scanned": len(posts),
        "auto_finalized": False,
    }


def list_matches(
    db: Session, *, tenant_id: UUID, status: str | None = "proposed"
) -> list[SocialMatch]:
    stmt = (
        select(SocialMatch)
        .where(SocialMatch.tenant_id == tenant_id)
        .options(selectinload(SocialMatch.post).selectinload(SocialPost.account))
        .order_by(SocialMatch.created_at.desc())
    )
    if status:
        stmt = stmt.where(SocialMatch.status == status)
    return list(db.scalars(stmt).all())


def set_match_decision(
    db: Session,
    *,
    tenant_id: UUID,
    match_id: UUID,
    actor_id: UUID,
    status: str,
    note: str | None = None,
) -> SocialMatch:
    match = db.scalar(
        select(SocialMatch).where(SocialMatch.id == match_id, SocialMatch.tenant_id == tenant_id)
    )
    if match is None:
        raise KeyError("Social match not found")
    if status not in {"proposed", "included", "excluded"}:
        raise ValueError("Invalid social match status")
    match.status = status
    if note is not None:
        match.reviewer_note = note
    match.reviewed_by = actor_id
    match.reviewed_at = datetime.now(UTC)
    write_audit(
        db,
        tenant_id=tenant_id,
        actor_id=str(actor_id),
        action="social.match_decision",
        resource_type="social_match",
        resource_id=str(match.id),
        details={"status": status},
    )
    db.commit()
    db.refresh(match)
    return match


def gate_status_dict(db: Session) -> dict[str, Any]:
    gate = get_or_create_x_gate(db)
    ok, missing = gates_allow_live(db)
    settings = get_settings()
    return {
        "platform": gate.platform,
        "credentials_available": gate.credentials_available,
        "pricing_reviewed": gate.pricing_reviewed,
        "endpoints_confirmed": gate.endpoints_confirmed,
        "terms_documented": gate.terms_documented,
        "cost_approved": gate.cost_approved,
        "live_enabled": gate.live_enabled,
        "env_live_enabled": settings.x_api_live_enabled,
        "env_bearer_present": bool(settings.x_api_bearer_token),
        "env_mode": settings.x_api_mode,
        "live_ready": ok,
        "missing": missing,
        "notes": gate.notes,
        "checklist": gate.checklist,
        "scrape_forbidden": True,
    }
