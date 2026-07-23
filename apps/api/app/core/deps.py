from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.tenancy import Role, Tenant
from app.models.users import TenantUser

bearer_scheme = HTTPBearer(auto_error=False)
T = TypeVar("T")


@dataclass
class AuthContext:
    user: TenantUser
    tenant: Tenant
    role_code: str

    @property
    def tenant_id(self) -> UUID:
        return self.tenant.id


def get_current_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(payload["sub"])
        tenant_id = UUID(payload["tenant_id"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    user = db.get(TenantUser, user_id)
    tenant = db.get(Tenant, tenant_id)
    if user is None or tenant is None or not user.is_active or user.tenant_id != tenant.id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    role = db.get(Role, user.role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Role missing")
    return AuthContext(user=user, tenant=tenant, role_code=role.code)


def require_roles(*allowed: str) -> Callable[[AuthContext], AuthContext]:
    def _inner(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if auth.role_code not in allowed and auth.role_code != "platform_admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return auth

    return _inner


def tenant_scoped_get(model: type[T], db: Session, auth: AuthContext, object_id: UUID) -> T:
    obj = db.scalar(select(model).where(model.id == object_id, model.tenant_id == auth.tenant_id))  # type: ignore[attr-defined]
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj
