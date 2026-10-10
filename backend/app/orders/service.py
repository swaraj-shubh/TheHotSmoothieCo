import secrets
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidStateTransition, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.coupons import service as coupons
from app.inventory import service as inventory
from app.notifications import service as notifications
from app.orders.models import TRANSITIONS, Order, OrderStatus, OrderStatusHistory
from app.orders.schemas import OrderSummary

log = structlog.get_logger()
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # no 0/O/1/I/L: easy to read over the phone


class OrderNotFound(NotFound):
    code, message = "ORDER_NOT_FOUND", "Order not found"


def new_order_number() -> str:
    # Random, not sequential: doesn't reveal sales volume. 31^8 ≈ 8.5e11 — collisions are
    # effectively impossible and would still be caught by the unique constraint.
    return "HSC-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))


def record_transition(
    db: AsyncSession,
    order: Order,
    to: OrderStatus,
    *,
    note: str | None = None,
    actor_id: uuid.UUID | None = None,
) -> None:
    """The only way an order's status changes. Caller must hold the row lock (get_for_update)."""
    current = OrderStatus(order.status) if order.status else None
    if current is not None and to not in TRANSITIONS[current]:
        raise InvalidStateTransition(f"Order cannot move from {current} to {to}")
    order.status = to
    now = datetime.now(UTC)
    if to == OrderStatus.CONFIRMED:
        order.paid_at = order.paid_at or now
    if to == OrderStatus.CANCELLED:
        order.cancelled_at = now
    db.add(
        OrderStatusHistory(
            order_id=order.id, from_status=current, to_status=to, note=note, actor_user_id=actor_id
        )
    )
    if template := _notify_template(current, to):
        notifications.add_order_notification(db, order, template)


PAID_BEFORE_DISPATCH = {OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.PACKED}


def _notify_template(current: OrderStatus | None, to: OrderStatus) -> str | None:
    """Which status changes the customer hears about (refunds are notified per refund, in payments)."""
    if to == OrderStatus.CONFIRMED:
        return "order_confirmed"
    if to == OrderStatus.SHIPPED:
        return "order_shipped"
    if to == OrderStatus.DELIVERED and current != OrderStatus.RETURN_REQUESTED:  # not "return rejected"
        return "order_delivered"
    if to == OrderStatus.CANCELLED and current in PAID_BEFORE_DISPATCH:  # unpaid expiries stay quiet
        return "order_cancelled"
    return None


FORWARD_PATH = [
    OrderStatus.CONFIRMED,
    OrderStatus.PROCESSING,
    OrderStatus.PACKED,
    OrderStatus.SHIPPED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
]


def advance(
    db: AsyncSession, order: Order, target: OrderStatus, *, note: str, actor_id: uuid.UUID | None = None
) -> bool:
    """Move forward along the fulfilment path (couriers skip/merge scans), jumping straight to the
    target whenever that's a legal move so history doesn't invent steps. Never moves backwards."""
    current = OrderStatus(order.status)
    if current not in FORWARD_PATH or target not in FORWARD_PATH:
        return False
    if FORWARD_PATH.index(target) <= FORWARD_PATH.index(current):
        return False
    while current != target:
        step = target if target in TRANSITIONS[current] else FORWARD_PATH[FORWARD_PATH.index(current) + 1]
        record_transition(db, order, step, note=note, actor_id=actor_id)
        current = step
    return True


async def get_for_update(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID | None = None) -> Order:
    stmt = (
        select(Order).where(Order.id == order_id).with_for_update().execution_options(populate_existing=True)
    )
    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)  # customers only ever see their own orders
    order = await db.scalar(stmt)
    if order is None:
        raise OrderNotFound()
    return order


async def get_for_user(db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID) -> Order:
    order = await db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise OrderNotFound()
    return order


async def list_for_user(
    db: AsyncSession, user_id: uuid.UUID, cursor: str | None, limit: int
) -> Page[OrderSummary]:
    stmt = select(Order).where(Order.user_id == user_id)
    if cursor:
        ts, oid = decode_cursor(cursor, 2)
        stmt = stmt.where(tuple_(Order.created_at, Order.id) < (datetime.fromisoformat(ts), uuid.UUID(oid)))
    rows = list(await db.scalars(stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1)))
    items = [
        OrderSummary.model_validate(o).model_copy(update={"item_count": sum(i.quantity for i in o.items)})
        for o in rows[:limit]
    ]
    nxt = encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None
    return Page(items=items, next_cursor=nxt)


async def void_unpaid(
    db: AsyncSession, order: Order, to: OrderStatus, note: str, *, expired: bool = False
) -> None:
    """Shared by customer cancel and the expiry sweep: hand stock and the coupon back."""
    record_transition(db, order, to, note=note)
    await inventory.release_reservation(db, order.id, expired=expired)
    await coupons.release(db, order.id)


async def expire_unpaid(db: AsyncSession, limit: int = 100) -> int:
    """Cancel orders whose payment window lapsed. Run periodically by the worker; SKIP LOCKED makes
    concurrent sweepers safe, and an order being paid right now (row locked) is simply skipped."""
    orders = list(
        await db.scalars(
            select(Order)
            .where(Order.status == OrderStatus.PENDING_PAYMENT, Order.payment_due_at < datetime.now(UTC))
            .order_by(Order.payment_due_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for order in orders:
        await void_unpaid(db, order, OrderStatus.CANCELLED, "Payment window expired", expired=True)
    await db.commit()
    if orders:
        log.info("orders_expired", count=len(orders))
    return len(orders)
