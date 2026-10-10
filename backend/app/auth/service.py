import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from redis.exceptions import RedisError
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import TokenPurpose, UserSession, UserToken
from app.auth.schemas import RegisterIn, TokenOut
from app.core import security
from app.core.config import get_settings
from app.core.exceptions import AppError, Conflict, Forbidden, RateLimited, Unauthorized
from app.core.redis import redis
from app.notifications import service as notifications
from app.users import repository as users_repo
from app.users.models import User

log = structlog.get_logger()


class InvalidCredentials(Unauthorized):
    code, message = "INVALID_CREDENTIALS", "Invalid email or password"


class InvalidToken(AppError):
    code, message = "INVALID_TOKEN", "This link is invalid or has expired"


class SessionExpired(Unauthorized):
    code, message = "SESSION_EXPIRED", "Your session has expired, please log in again"


class AccountDisabled(Forbidden):
    code, message = "ACCOUNT_DISABLED", "This account has been deactivated"


class EmailTaken(Conflict):
    code, message = "EMAIL_TAKEN", "An account with this email already exists"


def _now() -> datetime:
    return datetime.now(UTC)


async def _start_session(db: AsyncSession, user: User, user_agent: str | None, ip: str | None) -> TokenOut:
    s = get_settings()
    refresh = security.new_opaque_token()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=security.hash_token(refresh),
        user_agent=(user_agent or "")[:512] or None,
        ip_address=ip,
        expires_at=_now() + timedelta(seconds=s.refresh_token_ttl_seconds),
        last_used_at=_now(),
    )
    db.add(session)
    await db.flush()
    return TokenOut(
        access_token=security.create_access_token(user.id, session.id),
        refresh_token=refresh,
        expires_in=s.access_token_ttl_seconds,
    )


async def _issue_email_token(db: AsyncSession, user: User, purpose: TokenPurpose, ttl: int) -> str:
    token = security.new_opaque_token()
    db.add(
        UserToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=security.hash_token(token),
            expires_at=_now() + timedelta(seconds=ttl),
        )
    )
    await db.flush()
    return token


async def _consume_email_token(db: AsyncSession, token: str, purpose: TokenPurpose) -> User:
    # Atomic single-use: the UPDATE only matches an unused, unexpired token, so two concurrent
    # submissions of the same link can't both succeed.
    user_id = await db.scalar(
        update(UserToken)
        .where(
            UserToken.token_hash == security.hash_token(token),
            UserToken.purpose == purpose,
            UserToken.used_at.is_(None),
            UserToken.expires_at > _now(),
        )
        .values(used_at=_now())
        .returning(UserToken.user_id)
    )
    user = user_id and await users_repo.get_by_id(db, user_id)
    if not user:
        raise InvalidToken()
    return user


async def send_verification_email(db: AsyncSession, user: User) -> None:
    s = get_settings()
    token = await _issue_email_token(db, user, TokenPurpose.VERIFY_EMAIL, s.email_token_ttl_seconds)
    await notifications.enqueue(
        db,
        "verify_email",
        recipient=user.email,
        user_id=user.id,
        context={
            "name": user.full_name.split(" ")[0],
            "link": f"{s.frontend_url}/verify-email?token={token}",
        },
        dedupe_key=f"verify_email:{security.hash_token(token)}",
    )


async def register(db: AsyncSession, data: RegisterIn, user_agent: str | None, ip: str | None):
    user = User(
        email=data.email,
        password_hash=security.hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        roles=[],
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:  # unique index on email — also covers concurrent duplicate signups
        raise EmailTaken() from exc
    tokens = await _start_session(db, user, user_agent, ip)
    await send_verification_email(db, user)
    await db.commit()
    log.info("user_registered", user_id=str(user.id))
    return user, tokens


# Reuse interval: a just-rotated refresh token is still honoured briefly (without rotating) so
# concurrent refreshes from one browser don't look like token theft.
REFRESH_REUSE_GRACE = timedelta(seconds=30)

# Per-account brute-force guard (complements the per-IP limit, which distributed credential
# stuffing sidesteps). Checked *before* the password so a lucky guess during lockout still fails.
# Trade-off: an attacker can lock a real user out for the window; password reset still works.
LOGIN_FAILURE_LIMIT = 10
LOGIN_FAILURE_WINDOW = 15 * 60


def _failure_key(email: str) -> str:
    return f"login_fail:{hashlib.sha256(email.lower().encode()).hexdigest()}"  # no plain emails in Redis


async def _check_login_lock(email: str) -> None:
    try:
        failures = int(await redis.get(_failure_key(email)) or 0)
    except RedisError:
        return  # fail open: per-IP limit still applies
    if failures >= LOGIN_FAILURE_LIMIT:
        raise RateLimited(
            "Too many failed attempts; try again in 15 minutes or reset your password", code="LOGIN_LOCKED"
        )


async def _record_login_failure(email: str) -> None:
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(_failure_key(email))
            pipe.expire(_failure_key(email), LOGIN_FAILURE_WINDOW, nx=True)
            await pipe.execute()
    except RedisError:
        pass


async def login(db: AsyncSession, email: str, password: str, user_agent: str | None, ip: str | None):
    await _check_login_lock(email)
    user = await users_repo.get_by_email(db, email)
    # verify_password runs a real hash even when the user doesn't exist (no timing oracle).
    if not security.verify_password(password, user.password_hash if user else None) or not user:
        log.info("login_failed", email_domain=email.rsplit("@", 1)[-1])
        await _record_login_failure(email)
        raise InvalidCredentials()
    if not user.is_active:
        raise AccountDisabled()
    if security.password_needs_rehash(user.password_hash):  # type: ignore[arg-type]
        user.password_hash = security.hash_password(password)
    user.last_login_at = _now()
    try:
        await redis.delete(_failure_key(email))
    except RedisError:
        pass
    tokens = await _start_session(db, user, user_agent, ip)
    await db.commit()
    return user, tokens


async def refresh(db: AsyncSession, refresh_token: str) -> TokenOut:
    s = get_settings()
    token_hash = security.hash_token(refresh_token)
    session = await db.scalar(
        select(UserSession)
        .where(
            or_(UserSession.refresh_token_hash == token_hash, UserSession.previous_token_hash == token_hash)
        )
        .with_for_update()
    )
    if session is None or session.revoked_at is not None or session.expires_at <= _now():
        raise SessionExpired()

    replayed = session.previous_token_hash == token_hash
    if replayed and (session.last_used_at is None or _now() - session.last_used_at > REFRESH_REUSE_GRACE):
        # An already-rotated token replayed outside the grace window: assume theft, kill the session.
        session.revoked_at = _now()
        await db.commit()
        log.warning("refresh_token_reuse_detected", session_id=str(session.id), user_id=str(session.user_id))
        raise SessionExpired()

    user = await users_repo.get_by_id(db, session.user_id)
    if not user or not user.is_active:
        session.revoked_at = _now()
        await db.commit()
        raise SessionExpired()

    if replayed:
        # Within the grace window: a parallel request lost the refresh race (several tabs/requests
        # refreshing at once). Give it an access token but no new refresh token: the winner already
        # holds the current one, and rotating again would invalidate it.
        await db.commit()
        return TokenOut(
            access_token=security.create_access_token(user.id, session.id),
            refresh_token=None,
            expires_in=s.access_token_ttl_seconds,
        )

    new_refresh = security.new_opaque_token()
    session.previous_token_hash = token_hash
    session.refresh_token_hash = security.hash_token(new_refresh)
    session.last_used_at = _now()
    session.expires_at = _now() + timedelta(seconds=s.refresh_token_ttl_seconds)
    await db.commit()
    return TokenOut(
        access_token=security.create_access_token(user.id, session.id),
        refresh_token=new_refresh,
        expires_in=s.access_token_ttl_seconds,
    )


async def revoke_sessions(db: AsyncSession, user_id: uuid.UUID, session_id: uuid.UUID | None = None) -> int:
    """Revoke one session (logout / remove device) or all of a user's sessions."""
    stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
    if session_id:
        stmt = stmt.where(UserSession.id == session_id)
    result = await db.execute(stmt.values(revoked_at=_now()))
    await db.commit()
    return result.rowcount  # type: ignore[attr-defined]


async def list_sessions(db: AsyncSession, user_id: uuid.UUID) -> list[UserSession]:
    return list(
        await db.scalars(
            select(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > _now(),
            )
            .order_by(UserSession.last_used_at.desc())
            .limit(100)
        )
    )


async def verify_email(db: AsyncSession, token: str) -> None:
    user = await _consume_email_token(db, token, TokenPurpose.VERIFY_EMAIL)
    user.email_verified_at = user.email_verified_at or _now()
    await db.commit()


async def forgot_password(db: AsyncSession, email: str) -> None:
    """Always succeeds from the caller's view so it can't be used to discover accounts."""
    user = await users_repo.get_by_email(db, email)
    if not user or not user.is_active:
        return
    s = get_settings()
    token = await _issue_email_token(db, user, TokenPurpose.RESET_PASSWORD, s.password_reset_ttl_seconds)
    await notifications.enqueue(
        db,
        "password_reset",
        recipient=user.email,
        user_id=user.id,
        context={
            "name": user.full_name.split(" ")[0],
            "link": f"{s.frontend_url}/reset-password?token={token}",
        },
        dedupe_key=f"password_reset:{security.hash_token(token)}",
    )
    await db.commit()


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    user = await _consume_email_token(db, token, TokenPurpose.RESET_PASSWORD)
    user.password_hash = security.hash_password(new_password)
    # Proving inbox ownership also verifies the email.
    user.email_verified_at = user.email_verified_at or _now()
    await revoke_sessions(db, user.id)  # commits


async def change_password(
    db: AsyncSession, user: User, current_session_id: uuid.UUID, current: str, new: str
):
    if not security.verify_password(current, user.password_hash):
        raise InvalidCredentials("Current password is incorrect")
    user.password_hash = security.hash_password(new)
    # Sign out every other device, keep this one.
    await db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user.id,
            UserSession.id != current_session_id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )
    await db.commit()
