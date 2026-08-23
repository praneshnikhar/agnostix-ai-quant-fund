"""Minimal bearer authentication boundary over the existing User model.

The repository has users/roles but no login or session service yet. Provider
management therefore requires a signed development/service bearer token. This
does not claim to be a complete identity provider; it prevents anonymous
provider access and keeps ownership tied to the existing User row.
"""

from __future__ import annotations

import hashlib
import hmac
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import User, UserRole
from app.db.session import get_session

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    role: str


def issue_access_token(user_id: uuid.UUID, auth_secret: str | None = None) -> str:
    """Create a service token for a known user; no endpoint exposes this."""
    secret = (auth_secret or get_settings().auth_secret).encode()
    subject = str(user_id)
    signature = hmac.new(secret, subject.encode(), hashlib.sha256).hexdigest()
    return f"{subject}.{signature}"


def _verify_token(token: str, auth_secret: str) -> uuid.UUID | None:
    subject, separator, signature = token.partition(".")
    if not separator or not signature:
        return None
    try:
        user_id = uuid.UUID(subject)
    except ValueError:
        return None
    expected = hmac.new(auth_secret.encode(), subject.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return user_id


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required"
        )
    user_id = _verify_token(credentials.credentials, get_settings().auth_secret)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication"
        )
    user = await session.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid authentication"
        )
    return CurrentUser(id=user.id, role=user.role)


def require_provider_read(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in {UserRole.VIEWER.value, UserRole.PM.value, UserRole.ADMIN.value}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="provider read forbidden")
    return user


def require_provider_write(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in {UserRole.PM.value, UserRole.ADMIN.value}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="provider write forbidden"
        )
    return user


def require_provider_delete(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="provider deletion forbidden"
        )
    return user
