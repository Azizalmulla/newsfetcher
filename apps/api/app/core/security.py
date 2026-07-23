from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return str(pwd_context.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    return bool(pwd_context.verify(password, password_hash))


def create_access_token(
    *,
    subject: str,
    tenant_id: UUID,
    role_code: str,
    expires_minutes: int | None = None,
) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": str(tenant_id),
        "role": role_code,
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
