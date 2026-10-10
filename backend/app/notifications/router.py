import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import delete, select

from app.auth.dependencies import DB, CurrentUser, require_roles
from app.core.exceptions import NotFound
from app.core.pagination import MAX_LIMIT, Page
from app.notifications import service
from app.notifications.models import Channel, NotificationStatus, NotificationTemplate
from app.notifications.templates import TEMPLATES
from app.users.models import RoleName, User

router = APIRouter(tags=["notifications"])
Support = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.CUSTOMER_SUPPORT))]
Marketing = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.MARKETING_MANAGER))]


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    channel: str
    template: str
    subject: str | None
    status: str
    created_at: datetime
    sent_at: datetime | None


class AdminNotificationOut(NotificationOut):
    user_id: uuid.UUID | None
    recipient: str
    attempts: int
    last_error: str | None
    next_attempt_at: datetime


class TemplateOut(BaseModel):
    code: str
    subject: str
    body: str
    is_overridden: bool
    is_active: bool
    placeholders: list[str]


class TemplateIn(BaseModel):
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    body: Annotated[str, StringConstraints(min_length=1, max_length=20_000)]
    is_active: bool = True


@router.get("/notifications", response_model=Page[NotificationOut])
async def my_notifications(
    user: CurrentUser,
    db: DB,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
):
    return await service.list_notifications(db, user_id=user.id, cursor=cursor, limit=limit)


@router.get("/admin/notifications", response_model=Page[AdminNotificationOut], tags=["admin: notifications"])
async def all_notifications(
    _: Support,
    db: DB,
    status_: Annotated[NotificationStatus | None, Query(alias="status")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    """`?status=FAILED` is the dead-letter list."""
    return await service.list_notifications(db, status=status_, cursor=cursor, limit=limit)


@router.post(
    "/admin/notifications/{notification_id}/retry",
    response_model=AdminNotificationOut,
    tags=["admin: notifications"],
)
async def retry(notification_id: uuid.UUID, _: Support, db: DB):
    return await service.retry(db, notification_id)


async def _template_out(db, code: str) -> TemplateOut:
    built_in = TEMPLATES[code]
    override = await db.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.code == code, NotificationTemplate.channel == Channel.EMAIL
        )
    )
    return TemplateOut(
        code=code,
        subject=override.subject if override else built_in.subject,
        body=override.body if override else built_in.body,
        is_overridden=override is not None,
        is_active=override.is_active if override else True,
        placeholders=sorted(service.allowed_placeholders(code)),
    )


@router.get("/admin/notification-templates", response_model=list[TemplateOut], tags=["admin: notifications"])
async def list_templates(_: Marketing, db: DB):
    return [await _template_out(db, code) for code in TEMPLATES]


@router.put("/admin/notification-templates/{code}", response_model=TemplateOut, tags=["admin: notifications"])
async def edit_template(code: str, data: TemplateIn, _: Marketing, db: DB):
    await service.upsert_template(db, code, data.subject, data.body, data.is_active)
    return await _template_out(db, code)


@router.delete(
    "/admin/notification-templates/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin: notifications"],
)
async def reset_template(code: str, _: Marketing, db: DB):
    """Revert to the built-in wording."""
    if code not in TEMPLATES:
        raise NotFound("Unknown template", code="TEMPLATE_NOT_FOUND")
    await db.execute(delete(NotificationTemplate).where(NotificationTemplate.code == code))
    await db.commit()
