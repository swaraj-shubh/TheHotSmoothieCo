import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.models import Banner, BannerPlacement
from app.audit.models import AuditLog
from app.auth.service import revoke_sessions
from app.core.cache import cached, invalidate
from app.core.exceptions import AppError, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.orders.models import PAID_STATUSES, Order
from app.orders.schemas import OrderSummary
from app.users import repository as users_repo
from app.users.models import Address, RoleName, User, user_roles
from app.users.schemas import AddressOut

ORM = ConfigDict(from_attributes=True)


# ---------- Customers ----------


class CustomerRow(BaseModel):
    model_config = ORM
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    is_active: bool
    email_verified: bool = Field(validation_alias="is_email_verified")
    created_at: datetime
    last_login_at: datetime | None
    order_count: int = 0
    total_spent_paise: int = 0


class CustomerDetail(CustomerRow):
    preferences: dict
    addresses: list[AddressOut] = []
    recent_orders: list[OrderSummary] = []


class CustomerStatusIn(BaseModel):
    is_active: bool
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]


class CustomerNotFound(NotFound):
    code, message = "CUSTOMER_NOT_FOUND", "Customer not found"


_STAFF = select(user_roles.c.user_id)


async def _stats(db: AsyncSession, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    if not user_ids:
        return {}
    rows = await db.execute(
        select(Order.user_id, func.count(), func.coalesce(func.sum(Order.total_paise), 0))
        .where(Order.user_id.in_(user_ids), Order.status.in_(PAID_STATUSES))
        .group_by(Order.user_id)
    )
    return {uid: (n, total) for uid, n, total in rows}


async def list_customers(
    db: AsyncSession, q: str | None, cursor: str | None, limit: int
) -> Page[CustomerRow]:
    stmt = select(User).where(User.deleted_at.is_(None), User.id.not_in(_STAFF))
    if q:
        q = q.strip()
        like = q.replace("%", "").replace("_", r"\_") + "%"
        stmt = stmt.where(
            or_(User.email.ilike(like), User.full_name.ilike(f"%{like}"), User.phone.ilike(like))
        )
    if cursor:
        ts, uid = decode_cursor(cursor, 2)
        stmt = stmt.where(tuple_(User.created_at, User.id) < (datetime.fromisoformat(ts), uuid.UUID(uid)))
    users = list(await db.scalars(stmt.order_by(User.created_at.desc(), User.id.desc()).limit(limit + 1)))
    page = users[:limit]
    stats = await _stats(db, [u.id for u in page])
    items = [
        CustomerRow.model_validate(u).model_copy(
            update={
                "order_count": stats.get(u.id, (0, 0))[0],
                "total_spent_paise": stats.get(u.id, (0, 0))[1],
            }
        )
        for u in page
    ]
    nxt = encode_cursor(page[-1].created_at, page[-1].id) if len(users) > limit else None
    return Page(items=items, next_cursor=nxt)


async def _customer(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.scalar(
        select(User).where(User.id == user_id, User.deleted_at.is_(None), User.id.not_in(_STAFF))
    )
    if user is None:
        raise CustomerNotFound()
    return user


async def customer_detail(db: AsyncSession, user_id: uuid.UUID) -> CustomerDetail:
    user = await _customer(db, user_id)
    n, total = (await _stats(db, [user.id])).get(user.id, (0, 0))
    addresses = await db.scalars(
        select(Address).where(Address.user_id == user.id).order_by(Address.created_at)
    )
    orders = await db.scalars(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc()).limit(10)
    )
    return CustomerDetail.model_validate(user).model_copy(
        update={
            "order_count": n,
            "total_spent_paise": total,
            "addresses": [AddressOut.model_validate(a) for a in addresses],
            "recent_orders": [
                OrderSummary.model_validate(o).model_copy(
                    update={"item_count": sum(i.quantity for i in o.items)}
                )
                for o in orders
            ],
        }
    )


async def set_customer_status(db: AsyncSession, user_id: uuid.UUID, data: CustomerStatusIn) -> CustomerDetail:
    user = await _customer(db, user_id)
    user.is_active = data.is_active
    if not data.is_active:
        await revoke_sessions(db, user.id)  # signs them out everywhere, immediately (commits)
    await db.commit()
    return await customer_detail(db, user_id)


# ---------- Staff & roles ----------


class StaffOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    roles: list[str] = Field(validation_alias="role_list")
    last_login_at: datetime | None


class RolesIn(BaseModel):
    roles: list[RoleName] = Field(max_length=len(RoleName))


async def list_staff(db: AsyncSession) -> list[User]:
    return list(
        await db.scalars(
            select(User).where(User.id.in_(_STAFF), User.deleted_at.is_(None)).order_by(User.email).limit(500)
        )
    )


async def set_roles(db: AsyncSession, actor: User, user_id: uuid.UUID, roles: list[RoleName]) -> User:
    user = await users_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFound("User not found", code="USER_NOT_FOUND")
    if user.id == actor.id and RoleName.SUPER_ADMIN not in roles:
        raise AppError("You can't remove your own SUPER_ADMIN role", code="SELF_LOCKOUT")
    user.roles = await users_repo.get_roles(db, sorted(set(roles)))
    await db.commit()
    # Roles are read from the DB on every request, so the change applies immediately.
    return user


# ---------- Audit log ----------


class AuditOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_email: str | None
    actor_roles: list | None
    action: str
    path: str
    status_code: int
    target_type: str | None
    target_id: str | None
    request_id: str | None
    ip_address: str | None
    request_body: dict | None
    created_at: datetime


async def list_audit(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID | None,
    target_id: str | None,
    target_type: str | None,
    since: datetime | None,
    until: datetime | None,
    cursor: str | None,
    limit: int,
) -> Page[AuditOut]:
    stmt = select(AuditLog)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_id)
    if target_id:
        stmt = stmt.where(AuditLog.target_id == target_id)
    if target_type:
        stmt = stmt.where(AuditLog.target_type == target_type)
    if since:
        stmt = stmt.where(AuditLog.created_at >= since)
    if until:
        stmt = stmt.where(AuditLog.created_at < until)
    if cursor:
        ts, aid = decode_cursor(cursor, 2)
        stmt = stmt.where(
            tuple_(AuditLog.created_at, AuditLog.id) < (datetime.fromisoformat(ts), uuid.UUID(aid))
        )
    rows = list(
        await db.scalars(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit + 1))
    )
    items = [AuditOut.model_validate(r) for r in rows[:limit]]
    return Page(
        items=items,
        next_cursor=encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None,
    )


# ---------- Banners ----------

BANNERS_KEY = "cache:banners:v1"
HttpsUrl = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^https://", max_length=1024)]
# Links stay on-site (relative) or https: no javascript: URLs reach the storefront.
LinkUrl = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^(/[^/\\]|https://)", max_length=1024)
]


class BannerIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    subtitle: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    image_url: HttpsUrl
    mobile_image_url: HttpsUrl | None = None
    link_url: LinkUrl | None = None
    placement: BannerPlacement
    sort_order: int = 0
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _window(self) -> "BannerIn":
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class BannerOut(BannerIn):
    model_config = ORM
    id: uuid.UUID


async def public_banners(db: AsyncSession, placement: BannerPlacement) -> list[dict]:
    async def load() -> list[dict]:
        rows = await db.scalars(select(Banner).where(Banner.is_active.is_(True)).order_by(Banner.sort_order))
        return [BannerOut.model_validate(b).model_dump(mode="json") for b in rows]

    # Cache all active banners; the schedule window is applied per request so a sale banner
    # appears/disappears on time without waiting for the cache to expire.
    now = datetime.now(UTC)
    out = []
    for b in await cached(BANNERS_KEY, 300, load):
        starts = datetime.fromisoformat(b["starts_at"]) if b["starts_at"] else None
        ends = datetime.fromisoformat(b["ends_at"]) if b["ends_at"] else None
        if b["placement"] == placement and (not starts or starts <= now) and (not ends or now < ends):
            out.append(b)
    return out


async def list_banners(db: AsyncSession) -> list[Banner]:
    return list(await db.scalars(select(Banner).order_by(Banner.placement, Banner.sort_order).limit(500)))


async def save_banner(db: AsyncSession, data: BannerIn, banner_id: uuid.UUID | None = None) -> Banner:
    if banner_id:
        banner = await db.get(Banner, banner_id)
        if banner is None:
            raise NotFound("Banner not found", code="BANNER_NOT_FOUND")
        for k, v in data.model_dump().items():
            setattr(banner, k, v)
    else:
        banner = Banner(**data.model_dump())
        db.add(banner)
    await db.commit()
    await invalidate(BANNERS_KEY)
    return banner


async def delete_banner(db: AsyncSession, banner_id: uuid.UUID) -> None:
    banner = await db.get(Banner, banner_id)
    if banner is None:
        raise NotFound("Banner not found", code="BANNER_NOT_FOUND")
    await db.delete(banner)
    await db.commit()
    await invalidate(BANNERS_KEY)
