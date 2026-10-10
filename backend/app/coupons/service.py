import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Category, Product
from app.checkout.pricing import CouponNotApplicable, CouponTerms, Line, discount_for
from app.core.exceptions import AppError, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.coupons.models import Coupon, CouponUsage
from app.coupons.schemas import CouponIn, CouponOut, CouponPatch
from app.orders.models import PAID_STATUSES, Order


class InvalidCoupon(AppError):
    code, message = "INVALID_COUPON", "This coupon is not valid"


class CouponNotFound(NotFound):
    code, message = "COUPON_NOT_FOUND", "Coupon not found"


def terms(coupon: Coupon) -> CouponTerms:
    return CouponTerms(
        discount_type=coupon.discount_type,
        value=coupon.value,
        max_discount_paise=coupon.max_discount_paise,
        min_subtotal_paise=coupon.min_subtotal_paise,
        product_ids=frozenset(p.id for p in coupon.products),
        category_ids=frozenset(c.id for c in coupon.categories),
    )


async def _user_usage_count(db: AsyncSession, coupon_id: uuid.UUID, user_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count()).where(CouponUsage.coupon_id == coupon_id, CouponUsage.user_id == user_id)
        )
        or 0
    )


async def validate(
    db: AsyncSession, code: str, user_id: uuid.UUID | None, lines: list[Line]
) -> tuple[Coupon, CouponTerms]:
    """Every rule, with a customer-readable reason. Guests get the per-user checks at checkout
    (which requires login)."""
    coupon = await db.scalar(select(Coupon).where(Coupon.code == code.strip().upper()))
    now = datetime.now(UTC)
    if coupon is None or not coupon.is_active:
        raise InvalidCoupon("This coupon code doesn't exist")
    if coupon.starts_at and now < coupon.starts_at:
        raise InvalidCoupon("This coupon isn't active yet")
    if coupon.ends_at and now >= coupon.ends_at:
        raise InvalidCoupon("This coupon has expired")
    if coupon.usage_limit is not None and coupon.times_used >= coupon.usage_limit:
        raise InvalidCoupon("This coupon has been fully redeemed")
    if user_id is not None:
        if (
            coupon.per_user_limit is not None
            and await _user_usage_count(db, coupon.id, user_id) >= coupon.per_user_limit
        ):
            raise InvalidCoupon("You've already used this coupon")
        if coupon.first_order_only and await db.scalar(
            select(func.count()).where(Order.user_id == user_id, Order.status.in_(PAID_STATUSES))
        ):
            raise InvalidCoupon("This coupon is only valid on your first order")
    t = terms(coupon)
    try:
        discount_for(t, lines)
    except CouponNotApplicable as exc:
        raise InvalidCoupon(exc.reason) from exc
    return coupon, t


async def claim(
    db: AsyncSession, coupon: Coupon, user_id: uuid.UUID, order_id: uuid.UUID, discount: int
) -> None:
    """Record a redemption inside the checkout transaction.

    The conditional UPDATE both enforces the global limit atomically and row-locks the coupon, so
    the per-user count below can't race with the same user's parallel checkout."""
    claimed = await db.scalar(
        update(Coupon)
        .where(
            Coupon.id == coupon.id, (Coupon.usage_limit.is_(None)) | (Coupon.times_used < Coupon.usage_limit)
        )
        .values(times_used=Coupon.times_used + 1)
        .returning(Coupon.id)
    )
    if claimed is None:
        raise InvalidCoupon("This coupon has been fully redeemed")
    if (
        coupon.per_user_limit is not None
        and await _user_usage_count(db, coupon.id, user_id) >= coupon.per_user_limit
    ):
        raise InvalidCoupon("You've already used this coupon")
    db.add(CouponUsage(coupon_id=coupon.id, user_id=user_id, order_id=order_id, discount_paise=discount))
    await db.flush()


async def release(db: AsyncSession, order_id: uuid.UUID) -> None:
    """Undo a claim when an unpaid order is cancelled/expires. Idempotent."""
    coupon_id = await db.scalar(
        delete(CouponUsage).where(CouponUsage.order_id == order_id).returning(CouponUsage.coupon_id)
    )
    if coupon_id:
        await db.execute(
            update(Coupon).where(Coupon.id == coupon_id).values(times_used=Coupon.times_used - 1)
        )


# ---------- Admin ----------


def to_out(c: Coupon) -> CouponOut:
    return CouponOut.model_validate(c).model_copy(
        update={"product_ids": [p.id for p in c.products], "category_ids": [x.id for x in c.categories]}
    )


async def _get(db: AsyncSession, coupon_id: uuid.UUID) -> Coupon:
    c = await db.scalar(
        select(Coupon).where(Coupon.id == coupon_id).execution_options(populate_existing=True)
    )
    if c is None:
        raise CouponNotFound()
    return c


async def _set_scope(db: AsyncSession, c: Coupon, product_ids, category_ids) -> None:
    if product_ids is not None:
        c.products = list(await db.scalars(select(Product).where(Product.id.in_(product_ids))))
        if len(c.products) != len(set(product_ids)):
            raise AppError("Unknown product in coupon scope", code="INVALID_COUPON_SCOPE")
    if category_ids is not None:
        c.categories = list(await db.scalars(select(Category).where(Category.id.in_(category_ids))))
        if len(c.categories) != len(set(category_ids)):
            raise AppError("Unknown category in coupon scope", code="INVALID_COUPON_SCOPE")


async def create(db: AsyncSession, data: CouponIn) -> CouponOut:
    c = Coupon(
        **data.model_dump(exclude={"product_ids", "category_ids"}), times_used=0, products=[], categories=[]
    )
    db.add(c)
    await _set_scope(db, c, data.product_ids, data.category_ids)
    await db.commit()
    return to_out(await _get(db, c.id))


async def update_coupon(db: AsyncSession, coupon_id: uuid.UUID, data: CouponPatch) -> CouponOut:
    c = await _get(db, coupon_id)
    for k, v in data.model_dump(exclude_unset=True, exclude={"product_ids", "category_ids"}).items():
        setattr(c, k, v)
    if c.starts_at and c.ends_at and c.ends_at <= c.starts_at:
        raise AppError("ends_at must be after starts_at", code="VALIDATION_ERROR")
    await _set_scope(db, c, data.product_ids, data.category_ids)
    await db.commit()
    return to_out(await _get(db, c.id))


async def get(db: AsyncSession, coupon_id: uuid.UUID) -> CouponOut:
    return to_out(await _get(db, coupon_id))


async def list_coupons(
    db: AsyncSession, active: bool | None, cursor: str | None, limit: int
) -> Page[CouponOut]:
    stmt = select(Coupon)
    if active is not None:
        stmt = stmt.where(Coupon.is_active.is_(active))
    if cursor:
        ts, cid = decode_cursor(cursor, 2)
        stmt = stmt.where(tuple_(Coupon.created_at, Coupon.id) < (datetime.fromisoformat(ts), uuid.UUID(cid)))
    rows = list(await db.scalars(stmt.order_by(Coupon.created_at.desc(), Coupon.id.desc()).limit(limit + 1)))
    items = [to_out(c) for c in rows[:limit]]
    return Page(
        items=items,
        next_cursor=encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None,
    )
