"""Dashboard + analytics queries. Revenue is recognised when an order is paid (paid_at) and
refunds when they're processed, all bucketed in India time so "today" means today in IST."""

import enum
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Product, ProductStatus, ProductVariant
from app.core.cache import cached
from app.core.exceptions import AppError
from app.inventory.models import Inventory
from app.notifications.models import Notification, NotificationStatus
from app.orders.models import Order, OrderItem, OrderReturn, OrderStatus, ReturnStatus
from app.payments.models import Refund, RefundStatus, WebhookEvent, WebhookStatus
from app.reviews.models import Review, ReviewStatus
from app.users.models import User, user_roles

IST = ZoneInfo("Asia/Kolkata")
DASHBOARD_KEY = "cache:admin:dashboard:v1"


def ist_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=IST)


def _local(col):
    return func.timezone("Asia/Kolkata", col)  # timestamptz -> IST wall-clock time


# ---------- Dashboard ----------


async def _revenue_since(db: AsyncSession, since: datetime) -> dict:
    gross, orders = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total_paise), 0), func.count()).where(Order.paid_at >= since)
        )
    ).one()
    refunded: int = (
        await db.scalar(
            select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                Refund.status == RefundStatus.PROCESSED, Refund.processed_at >= since
            )
        )
        or 0
    )
    return {"orders": orders, "gross_paise": gross, "refunds_paise": refunded, "net_paise": gross - refunded}


async def dashboard(db: AsyncSession) -> dict:
    async def load() -> dict:
        today = ist_midnight(datetime.now(IST).date())
        statuses = dict((await db.execute(select(Order.status, func.count()).group_by(Order.status))).all())
        available = Inventory.on_hand - Inventory.reserved
        low, out = (
            await db.execute(
                select(
                    func.count().filter(available <= Inventory.low_stock_threshold, available > 0),
                    func.count().filter(available <= 0),
                )
                .select_from(Inventory)
                .join(ProductVariant, ProductVariant.id == Inventory.variant_id)
                .join(Product, Product.id == ProductVariant.product_id)
                .where(ProductVariant.is_active.is_(True), Product.status == ProductStatus.ACTIVE)
            )
        ).one()
        staff = select(user_roles.c.user_id)
        customers, new_customers = (
            await db.execute(
                select(
                    func.count(), func.count().filter(User.created_at >= today - timedelta(days=30))
                ).where(User.deleted_at.is_(None), User.id.not_in(staff))
            )
        ).one()
        pending_refund_paise = await db.scalar(
            select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                Refund.status == RefundStatus.PENDING
            )
        )
        products = dict(
            (await db.execute(select(Product.status, func.count()).group_by(Product.status))).all()
        )

        async def count(model, *where) -> int:
            return await db.scalar(select(func.count()).select_from(model).where(*where)) or 0

        return {
            "revenue": {
                "today": await _revenue_since(db, today),
                "last_7_days": await _revenue_since(db, today - timedelta(days=6)),
                "last_30_days": await _revenue_since(db, today - timedelta(days=29)),
            },
            "orders_by_status": statuses,
            "needs_attention": {
                "to_fulfil": statuses.get(OrderStatus.CONFIRMED, 0) + statuses.get(OrderStatus.PROCESSING, 0),
                "awaiting_pickup": statuses.get(OrderStatus.PACKED, 0),
                "return_requests": await count(OrderReturn, OrderReturn.status == ReturnStatus.REQUESTED),
                "refunds_pending": statuses.get(OrderStatus.REFUND_PENDING, 0),
                "refunds_pending_paise": pending_refund_paise,
                "reviews_to_moderate": await count(
                    Review, Review.status == ReviewStatus.PENDING, Review.deleted_at.is_(None)
                ),
                "failed_notifications": await count(
                    Notification, Notification.status == NotificationStatus.FAILED
                ),
                "failed_webhooks": await count(WebhookEvent, WebhookEvent.status == WebhookStatus.FAILED),
            },
            "inventory": {"low_stock_variants": low, "out_of_stock_variants": out},
            "customers": {"total": customers, "new_last_30_days": new_customers},
            "products": {s.lower(): products.get(s, 0) for s in ProductStatus},
            "generated_at": datetime.now(UTC).isoformat(),
        }

    # Short cache: a dashboard refreshed by several staff shouldn't hammer the aggregates.
    return await cached(DASHBOARD_KEY, 60, load)


# ---------- Analytics ----------


class Interval(enum.StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class SalesPoint(BaseModel):
    period: date
    orders: int
    gross_paise: int
    discount_paise: int
    refunds_paise: int
    net_paise: int
    average_order_paise: int


class TopProduct(BaseModel):
    product_id: str
    title: str
    units: int
    revenue_paise: int


def _check_range(start: date, end: date, interval: Interval) -> None:
    if end < start:
        raise AppError("`to` must be on or after `from`", code="INVALID_RANGE")
    limit = {Interval.DAY: 370, Interval.WEEK: 370 * 3, Interval.MONTH: 370 * 5}[interval]
    if (end - start).days > limit:
        raise AppError("Date range too large for this interval", code="INVALID_RANGE")


def _periods(start: date, end: date, interval: Interval) -> list[date]:
    if interval == Interval.DAY:
        first, step = start, lambda d: d + timedelta(days=1)
    elif interval == Interval.WEEK:  # ISO weeks start Monday, matching date_trunc('week')
        first, step = start - timedelta(days=start.weekday()), lambda d: d + timedelta(days=7)
    else:
        first = start.replace(day=1)

        def step(d: date) -> date:
            return date(d.year + d.month // 12, d.month % 12 + 1, 1)

    out, d = [], first
    while d <= end:
        out.append(d)
        d = step(d)
    return out


async def sales(db: AsyncSession, start: date, end: date, interval: Interval) -> list[SalesPoint]:
    _check_range(start, end, interval)
    lo, hi = ist_midnight(start), ist_midnight(end + timedelta(days=1))
    bucket = cast(func.date_trunc(interval.value, _local(Order.paid_at)), Date)
    orders = {
        row.period: row
        for row in (
            await db.execute(
                select(
                    bucket.label("period"),
                    func.count().label("orders"),
                    func.sum(Order.total_paise).label("gross"),
                    func.sum(Order.discount_paise).label("discount"),
                )
                .where(Order.paid_at >= lo, Order.paid_at < hi)
                .group_by(bucket)
            )
        ).all()
    }
    rbucket = cast(func.date_trunc(interval.value, _local(Refund.processed_at)), Date)
    refunds = dict(
        (
            await db.execute(
                select(rbucket, func.sum(Refund.amount_paise))
                .where(
                    Refund.status == RefundStatus.PROCESSED,
                    Refund.processed_at >= lo,
                    Refund.processed_at < hi,
                )
                .group_by(rbucket)
            )
        ).all()
    )
    series = []
    for period in _periods(start, end, interval):  # continuous: empty days show as zero, not gaps
        o = orders.get(period)
        n, gross = (o.orders, o.gross) if o else (0, 0)
        refunded = refunds.get(period, 0)
        series.append(
            SalesPoint(
                period=period,
                orders=n,
                gross_paise=gross,
                discount_paise=o.discount if o else 0,
                refunds_paise=refunded,
                net_paise=gross - refunded,
                average_order_paise=gross // n if n else 0,
            )
        )
    return series


async def top_products(db: AsyncSession, start: date, end: date, by: str, limit: int) -> list[TopProduct]:
    _check_range(start, end, Interval.MONTH)
    revenue = func.sum(OrderItem.line_total_paise)
    units = func.sum(OrderItem.quantity)
    rows = (
        await db.execute(
            select(OrderItem.product_id, func.max(OrderItem.product_title), units, revenue)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.paid_at >= ist_midnight(start), Order.paid_at < ist_midnight(end + timedelta(days=1))
            )
            .group_by(OrderItem.product_id)
            .order_by((units if by == "units" else revenue).desc())
            .limit(limit)
        )
    ).all()
    return [TopProduct(product_id=str(pid), title=t, units=u, revenue_paise=r) for pid, t, u, r in rows]


async def customer_stats(db: AsyncSession, start: date, end: date) -> dict:
    _check_range(start, end, Interval.MONTH)
    per_customer = (
        select(Order.user_id, func.count().label("n"))
        .where(Order.paid_at >= ist_midnight(start), Order.paid_at < ist_midnight(end + timedelta(days=1)))
        .group_by(Order.user_id)
        .subquery()
    )
    buyers, repeat, orders = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(per_customer.c.n >= 2),
                func.coalesce(func.sum(per_customer.c.n), 0),
            ).select_from(per_customer)
        )
    ).one()
    return {
        "buyers": buyers,
        "repeat_buyers": repeat,
        "repeat_rate": round(repeat / buyers, 4) if buyers else 0.0,
        "orders_per_buyer": round(orders / buyers, 2) if buyers else 0.0,
    }
