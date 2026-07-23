from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, get_current_auth, require_roles
from app.db.session import get_db
from app.models.social import SocialAccount, SocialMatch
from app.services import social as social_service

router = APIRouter(prefix="/social", tags=["social"])


class GateOut(BaseModel):
    platform: str
    credentials_available: bool
    pricing_reviewed: bool
    endpoints_confirmed: bool
    terms_documented: bool
    cost_approved: bool
    live_enabled: bool
    env_live_enabled: bool
    env_bearer_present: bool
    env_mode: str
    live_ready: bool
    missing: list[str]
    notes: str | None
    scrape_forbidden: bool


class GateUpdateIn(BaseModel):
    credentials_available: bool | None = None
    pricing_reviewed: bool | None = None
    endpoints_confirmed: bool | None = None
    terms_documented: bool | None = None
    cost_approved: bool | None = None
    live_enabled: bool | None = None
    notes: str | None = None


class AccountOut(BaseModel):
    id: UUID
    platform: str
    handle: str
    display_name: str | None
    account_type: str
    is_approved: bool
    is_active: bool


class ApprovalIn(BaseModel):
    approved: bool


class FixturePostIn(BaseModel):
    text: str = Field(min_length=1)
    external_post_id: str | None = None


class FixtureIngestIn(BaseModel):
    handle: str
    posts: list[FixturePostIn] = Field(min_length=1)


class MatchOut(BaseModel):
    id: UUID
    entity_id: UUID
    post_id: UUID
    status: str
    best_match_type: str
    best_score: float
    matched_term: str
    snippet: str | None
    reviewer_note: str | None
    reviewed_at: datetime | None
    post_text: str | None = None
    post_permalink: str | None = None
    account_handle: str | None = None


class DecisionIn(BaseModel):
    status: str = Field(pattern=r"^(proposed|included|excluded)$")
    note: str | None = None


def _account_out(row: SocialAccount) -> AccountOut:
    return AccountOut(
        id=row.id,
        platform=row.platform,
        handle=row.handle,
        display_name=row.display_name,
        account_type=row.account_type,
        is_approved=row.is_approved,
        is_active=row.is_active,
    )


def _match_out(row: SocialMatch) -> MatchOut:
    post = row.post
    account = post.account if post else None
    return MatchOut(
        id=row.id,
        entity_id=row.entity_id,
        post_id=row.post_id,
        status=row.status,
        best_match_type=row.best_match_type,
        best_score=row.best_score,
        matched_term=row.matched_term,
        snippet=row.snippet,
        reviewer_note=row.reviewer_note,
        reviewed_at=row.reviewed_at,
        post_text=post.text if post else None,
        post_permalink=post.permalink if post else None,
        account_handle=account.handle if account else None,
    )


@router.get("/x/gate", response_model=GateOut)
def get_gate(db: Session = Depends(get_db)) -> GateOut:
    return GateOut(**social_service.gate_status_dict(db))


@router.put("/x/gate", response_model=GateOut)
def put_gate(
    payload: GateUpdateIn,
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> GateOut:
    try:
        social_service.update_x_gate(
            db,
            actor_id=str(auth.user.id),
            credentials_available=payload.credentials_available,
            pricing_reviewed=payload.pricing_reviewed,
            endpoints_confirmed=payload.endpoints_confirmed,
            terms_documented=payload.terms_documented,
            cost_approved=payload.cost_approved,
            live_enabled=payload.live_enabled,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GateOut(**social_service.gate_status_dict(db))


@router.get("/accounts", response_model=list[AccountOut])
def get_accounts(
    approved_only: bool = Query(default=False),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[AccountOut]:
    _ = auth
    return [
        _account_out(row)
        for row in social_service.list_accounts(db, approved_only=approved_only)
    ]


@router.post("/accounts/{account_id}/approval", response_model=AccountOut)
def approve_account(
    account_id: UUID,
    payload: ApprovalIn,
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> AccountOut:
    try:
        account = social_service.set_account_approval(
            db, account_id=account_id, actor_id=str(auth.user.id), approved=payload.approved
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Social account not found") from exc
    return _account_out(account)


@router.post("/fixture-ingest")
def fixture_ingest(
    payload: FixtureIngestIn,
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        return social_service.ingest_fixture_posts(
            db,
            handle=payload.handle,
            posts=[row.model_dump() for row in payload.posts],
            actor_id=str(auth.user.id),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/poll")
def poll_live(
    auth: AuthContext = Depends(require_roles("platform_admin", "tenant_admin")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """Official API poll only. Returns gates_incomplete when checklist is unfinished."""
    return social_service.poll_approved_accounts(db, actor_id=str(auth.user.id))


@router.post("/match")
def run_match(
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return social_service.match_posts_for_tenant(db, tenant_id=auth.tenant_id)


@router.get("/matches", response_model=list[MatchOut])
def get_matches(
    status: str | None = Query(default="proposed"),
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> list[MatchOut]:
    return [
        _match_out(row)
        for row in social_service.list_matches(db, tenant_id=auth.tenant_id, status=status)
    ]


@router.post("/matches/{match_id}/decision", response_model=MatchOut)
def decide_match(
    match_id: UUID,
    payload: DecisionIn,
    auth: AuthContext = Depends(require_roles("tenant_admin", "editor_reviewer")),
    db: Session = Depends(get_db),
) -> MatchOut:
    try:
        match = social_service.set_match_decision(
            db,
            tenant_id=auth.tenant_id,
            match_id=match_id,
            actor_id=auth.user.id,
            status=payload.status,
            note=payload.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Social match not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    loaded = social_service.list_matches(db, tenant_id=auth.tenant_id, status=None)
    row = next((item for item in loaded if item.id == match.id), match)
    return _match_out(row)
