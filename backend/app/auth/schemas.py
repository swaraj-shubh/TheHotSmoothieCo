import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.users.schemas import Name, NormalizedEmail, Phone, UserOut

# Upper bound stops multi-megabyte passwords being fed to Argon2 (CPU DoS).
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
OpaqueToken = Annotated[str, StringConstraints(min_length=20, max_length=256)]


class RegisterIn(BaseModel):
    email: NormalizedEmail
    password: Password
    full_name: Name
    phone: Phone | None = None


class LoginIn(BaseModel):
    email: NormalizedEmail
    password: Annotated[str, StringConstraints(max_length=128)]


class RefreshIn(BaseModel):
    refresh_token: OpaqueToken


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str | None  # None only on a grace-window refresh: keep using the current one
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class AuthOut(TokenOut):
    user: UserOut


class EmailIn(BaseModel):
    email: NormalizedEmail


class TokenIn(BaseModel):
    token: OpaqueToken


class ResetPasswordIn(BaseModel):
    token: OpaqueToken
    new_password: Password


class ChangePasswordIn(BaseModel):
    current_password: Annotated[str, StringConstraints(max_length=128)]
    new_password: Password


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    current: bool = False
