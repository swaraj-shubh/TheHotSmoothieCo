import uuid

from fastapi import APIRouter, Depends, Request, status

from app.auth import service
from app.auth.dependencies import DB, CurrentPrincipal, CurrentUser
from app.auth.schemas import (
    AuthOut,
    ChangePasswordIn,
    EmailIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    SessionOut,
    TokenIn,
    TokenOut,
)
from app.core.clientip import client_ip
from app.core.ratelimit import rate_limit
from app.users.schemas import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _client(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), client_ip(request.scope)


def _auth_out(user, tokens: TokenOut) -> AuthOut:
    return AuthOut(**tokens.model_dump(), user=UserOut.model_validate(user))


@router.post(
    "/register",
    response_model=AuthOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("register", 5, 3600))],
)
async def register(data: RegisterIn, request: Request, db: DB):
    user, tokens = await service.register(db, data, *_client(request))
    return _auth_out(user, tokens)


@router.post("/login", response_model=AuthOut, dependencies=[Depends(rate_limit("login", 10, 300))])
async def login(data: LoginIn, request: Request, db: DB):
    user, tokens = await service.login(db, data.email, data.password, *_client(request))
    return _auth_out(user, tokens)


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(rate_limit("refresh", 30, 300))])
async def refresh(data: RefreshIn, db: DB):
    return await service.refresh(db, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(principal: CurrentPrincipal, db: DB):
    await service.revoke_sessions(db, principal.user.id, principal.session_id)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(user: CurrentUser, db: DB):
    await service.revoke_sessions(db, user.id)


@router.get("/sessions", response_model=list[SessionOut])
async def sessions(principal: CurrentPrincipal, db: DB):
    rows = await service.list_sessions(db, principal.user.id)
    return [
        SessionOut.model_validate(s).model_copy(update={"current": s.id == principal.session_id})
        for s in rows
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(session_id: uuid.UUID, user: CurrentUser, db: DB):
    await service.revoke_sessions(db, user.id, session_id)


@router.post(
    "/verify-email",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("verify", 20, 3600))],
)
async def verify_email(data: TokenIn, db: DB):
    await service.verify_email(db, data.token)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("resend_verify", 3, 3600))],
)
async def resend_verification(user: CurrentUser, db: DB):
    if user.email_verified_at is None:
        await service.send_verification_email(db, user)
        await db.commit()


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(rate_limit("forgot_password", 5, 3600))],
)
async def forgot_password(data: EmailIn, db: DB):
    await service.forgot_password(db, data.email)
    return {"message": "If that account exists, a reset link has been sent"}


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("reset_password", 10, 3600))],
)
async def reset_password(data: ResetPasswordIn, db: DB):
    await service.reset_password(db, data.token, data.new_password)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("change_password", 10, 3600))],
)
async def change_password(data: ChangePasswordIn, principal: CurrentPrincipal, db: DB):
    await service.change_password(
        db, principal.user, principal.session_id, data.current_password, data.new_password
    )
