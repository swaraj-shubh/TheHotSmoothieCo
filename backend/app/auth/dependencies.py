import uuid
from datetime import UTC, datetime
from typing import Annotated, NamedTuple

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserSession
from app.core.database import get_db
from app.core.exceptions import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.users.models import RoleName, User

_bearer = HTTPBearer(auto_error=False)
DB = Annotated[AsyncSession, Depends(get_db)]


class Principal(NamedTuple):
    user: User
    session_id: uuid.UUID


async def get_principal(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> Principal:
    if creds is None:
        raise Unauthorized()
    try:
        claims = decode_access_token(creds.credentials)
        user_id, session_id = uuid.UUID(claims["sub"]), uuid.UUID(claims["sid"])
    except (jwt.PyJWTError, ValueError) as exc:
        raise Unauthorized("Invalid or expired token", code="INVALID_TOKEN") from exc

    # One query checks the session is live and the account is usable, so logout,
    # deactivation and deletion take effect immediately rather than at token expiry.
    user = await db.scalar(
        select(User)
        .join(UserSession, UserSession.user_id == User.id)
        .where(
            User.id == user_id,
            UserSession.id == session_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    )
    if user is None:
        raise Unauthorized("Session is no longer valid", code="INVALID_TOKEN")
    return Principal(user, session_id)


async def get_current_user(principal: Annotated[Principal, Depends(get_principal)]) -> User:
    return principal.user


async def get_optional_user(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User | None:
    """For endpoints open to guests. A *present but invalid* token is still a 401, so an expired
    session never silently degrades into a guest (which would hide the user's cart)."""
    if creds is None:
        return None
    return (await get_principal(db, creds)).user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentPrincipal = Annotated[Principal, Depends(get_principal)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: RoleName):
    """Backend-enforced RBAC. SUPER_ADMIN passes every check."""
    allowed = {r.value for r in roles} | {RoleName.SUPER_ADMIN.value}

    async def dependency(user: CurrentUser, request: Request) -> User:
        # Recorded before the check so the audit log also captures *denied* attempts.
        request.state.actor = {"id": str(user.id), "email": user.email, "roles": user.role_list}
        if not allowed.intersection(user.role_list):
            raise Forbidden()
        return user

    return dependency
