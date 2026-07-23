from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import AuthContext, get_current_auth
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.tenancy import Role, Tenant
from app.models.users import TenantUser
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterTenantRequest(BaseModel):
    tenant_name: str = Field(min_length=2, max_length=255)
    tenant_slug: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9-]+$")
    admin_email: EmailStr
    admin_full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    tenant_slug: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tenant_id: UUID
    role: str


class MeResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    tenant_id: UUID
    tenant_slug: str
    role: str


@router.post("/register-tenant", response_model=TokenResponse, status_code=201)
def register_tenant(payload: RegisterTenantRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing = db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug))
    if existing:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    role = db.scalar(select(Role).where(Role.code == "tenant_admin"))
    if role is None:
        raise HTTPException(status_code=500, detail="Roles not seeded")

    tenant = Tenant(slug=payload.tenant_slug, name=payload.tenant_name, status="active")
    db.add(tenant)
    db.flush()

    user = TenantUser(
        tenant_id=tenant.id,
        role_id=role.id,
        email=payload.admin_email.lower(),
        full_name=payload.admin_full_name,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    write_audit(
        db,
        tenant_id=tenant.id,
        actor_id=None,
        action="tenant.registered",
        resource_type="tenant",
        resource_id=str(tenant.id),
        details={"slug": tenant.slug, "admin_email": user.email},
    )
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), tenant_id=tenant.id, role_code=role.code)
    return TokenResponse(access_token=token, tenant_id=tenant.id, role=role.code)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    tenant = db.scalar(select(Tenant).where(Tenant.slug == payload.tenant_slug))
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    user = db.scalar(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant.id,
            TenantUser.email == payload.email.lower(),
        )
    )
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    role = db.get(Role, user.role_id)
    if role is None:
        raise HTTPException(status_code=500, detail="Role missing")
    write_audit(
        db,
        tenant_id=tenant.id,
        actor_id=str(user.id),
        action="auth.login",
        resource_type="tenant_user",
        resource_id=str(user.id),
    )
    db.commit()
    token = create_access_token(subject=str(user.id), tenant_id=tenant.id, role_code=role.code)
    return TokenResponse(access_token=token, tenant_id=tenant.id, role=role.code)


@router.get("/me", response_model=MeResponse)
def me(auth: AuthContext = Depends(get_current_auth)) -> MeResponse:
    return MeResponse(
        user_id=auth.user.id,
        email=auth.user.email,
        full_name=auth.user.full_name,
        tenant_id=auth.tenant.id,
        tenant_slug=auth.tenant.slug,
        role=auth.role_code,
    )
