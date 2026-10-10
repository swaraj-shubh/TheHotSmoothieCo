"""Post-checkout order operations that span modules: cancellation (with refund + restock),
staff refunds, and returns. Kept apart from orders.service to avoid import cycles with payments."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.coupons import service as coupons
from app.inventory import service as inventory
from app.inventory.models import TxnType
from app.orders import service as orders
from app.orders.models import Order, OrderReturn, OrderStatus, OrderStatusHistory, ReturnStatus
from app.orders.schemas import (
    AdminOrderOut,
    AdminOrderRow,
    AdminRefundOut,
    AdminShipmentOut,
    PaymentSummary,
    ReturnOut,
)
from app.payments import service as payments
from app.payments.models import Payment, Refund
from app.payments.provider import PaymentProvider, PaymentProviderUnavailable
from app.shipping import service as shipping
from app.shipping.models import Shipment
from app.shipping.provider import ShipmentStatus, ShippingProvider, ShippingUnavailable

log = structlog.get_logger()


class CannotCancel(AppError):
    code, message = "CANNOT_CANCEL", "This order can no longer be cancelled online; please contact support"


class ReturnNotAllowed(AppError):
    code, message = "RETURN_NOT_ALLOWED", "This order can't be returned"


class ReturnNotFound(NotFound):
    code, message = "RETURN_NOT_FOUND", "Return not found"


CUSTOMER_CANCELLABLE = {OrderStatus.CONFIRMED, OrderStatus.PROCESSING}
STAFF_CANCELLABLE = {OrderStatus.CONFIRMED, OrderStatus.PROCESSING, OrderStatus.PACKED}


def _require[T](provider: T | None, unavailable: type[Exception]) -> T:
    if provider is None:
        raise unavailable()
    return provider


async def _restock(db: AsyncSession, order: Order, actor_id: uuid.UUID | None, why: str) -> None:
    for item in order.items:
        await inventory.adjust(
            db,
            item.variant_id,
            delta=item.quantity,
            reason=f"{why} {order.number}",
            actor_id=actor_id,
            type_=TxnType.RETURN,
        )


async def cancel(
    db: AsyncSession,
    order_id: uuid.UUID,
    *,
    reason: str,
    pay: PaymentProvider | None,
    ship: ShippingProvider | None,
    user_id: uuid.UUID | None = None,  # set = customer-initiated (ownership + stricter rules)
    actor_id: uuid.UUID | None = None,
    restock: bool = True,
) -> Order:
    order = await orders.get_for_update(db, order_id, user_id)
    status = OrderStatus(order.status)

    if status == OrderStatus.PENDING_PAYMENT:
        await orders.void_unpaid(db, order, OrderStatus.CANCELLED, reason)
    elif status in (CUSTOMER_CANCELLABLE if user_id else STAFF_CANCELLABLE):
        if shipment := await shipping.active_forward_shipment(db, order.id):
            if user_id:
                raise CannotCancel("Your order is already being shipped; please contact support")
            await shipping.cancel_shipment(db, _require(ship, ShippingUnavailable), shipment)
        payment = await payments.payment_for_order(db, order.id)
        orders.record_transition(db, order, OrderStatus.CANCELLED, note=reason, actor_id=actor_id)
        if restock:
            await _restock(db, order, actor_id, "cancelled")
        await coupons.release(db, order.id)
        await payments.create_refund(
            db,
            _require(pay, PaymentProviderUnavailable),
            order,
            payment,
            None,
            f"Order cancelled: {reason}"[:255],
            key=f"cancel:{order.id}",
            actor_id=actor_id,
        )
    else:
        raise CannotCancel()
    await db.commit()
    log.info(
        "order_cancelled", order_id=str(order.id), by="customer" if user_id else "staff", from_status=status
    )
    return order


async def staff_refund(
    db: AsyncSession,
    pay: PaymentProvider,
    order_id: uuid.UUID,
    amount: int | None,
    reason: str,
    key: str,
    actor_id: uuid.UUID,
) -> Refund:
    order = await orders.get_for_update(db, order_id)
    payment = await payments.payment_for_order(db, order.id)
    refund = await payments.create_refund(
        db, pay, order, payment, amount, reason, key=f"staff:{key}", actor_id=actor_id
    )
    await db.commit()
    return refund


# ---------- Returns ----------


async def _delivered_at(db: AsyncSession, order: Order) -> datetime | None:
    return await db.scalar(
        select(OrderStatusHistory.created_at)
        .where(OrderStatusHistory.order_id == order.id, OrderStatusHistory.to_status == OrderStatus.DELIVERED)
        .order_by(OrderStatusHistory.created_at.desc())
        .limit(1)
    )


async def request_return(
    db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID, reason: str
) -> OrderReturn:
    order = await orders.get_for_update(db, order_id, user_id)
    if order.status != OrderStatus.DELIVERED:
        raise ReturnNotAllowed("Only delivered orders can be returned")
    delivered = await _delivered_at(db, order)
    window = timedelta(days=get_settings().return_window_days)
    if delivered is None or datetime.now(UTC) - delivered > window:
        raise ReturnNotAllowed(f"Returns are accepted within {window.days} days of delivery")
    ret = OrderReturn(order_id=order.id, status=ReturnStatus.REQUESTED, reason=reason, restocked=False)
    db.add(ret)
    orders.record_transition(
        db, order, OrderStatus.RETURN_REQUESTED, note=f"Return requested: {reason}"[:500]
    )
    await db.commit()
    return ret


async def _get_return(db: AsyncSession, return_id: uuid.UUID) -> OrderReturn:
    ret = await db.scalar(select(OrderReturn).where(OrderReturn.id == return_id).with_for_update())
    if ret is None:
        raise ReturnNotFound()
    return ret


async def approve_return(
    db: AsyncSession,
    return_id: uuid.UUID,
    ship: ShippingProvider | None,
    schedule_pickup: bool,
    note: str | None,
) -> OrderReturn:
    ret = await _get_return(db, return_id)
    if ret.status != ReturnStatus.REQUESTED:
        raise ReturnNotAllowed(f"Return is {ret.status}")
    ret.status, ret.admin_note = ReturnStatus.APPROVED, note
    if schedule_pickup:
        provider = _require(ship, ShippingUnavailable)
        order = await orders.get_for_update(db, ret.order_id)
        package = shipping.package_for(order)
        created = await provider.create_shipment(shipping.snapshot(order), package, is_return=True)
        shipment = Shipment(
            order_id=order.id,
            provider=provider.name,
            provider_order_id=created.provider_order_id,
            provider_shipment_id=created.provider_shipment_id,
            status=ShipmentStatus.CREATED,
            weight_grams=package.weight_grams,
            is_return=True,
            events=[],
        )
        db.add(shipment)
        await db.flush()
        ret.shipment_id = shipment.id
    await db.commit()
    return ret


async def reject_return(
    db: AsyncSession, return_id: uuid.UUID, note: str, actor_id: uuid.UUID
) -> OrderReturn:
    ret = await _get_return(db, return_id)
    if ret.status not in (ReturnStatus.REQUESTED, ReturnStatus.APPROVED):
        raise ReturnNotAllowed(f"Return is {ret.status}")
    order = await orders.get_for_update(db, ret.order_id)
    ret.status, ret.admin_note = ReturnStatus.REJECTED, note
    orders.record_transition(
        db, order, OrderStatus.DELIVERED, note=f"Return rejected: {note}"[:500], actor_id=actor_id
    )
    await db.commit()
    return ret


async def receive_return(
    db: AsyncSession,
    pay: PaymentProvider,
    return_id: uuid.UUID,
    restock: bool,
    note: str | None,
    actor_id: uuid.UUID,
) -> OrderReturn:
    ret = await _get_return(db, return_id)
    if ret.status != ReturnStatus.APPROVED:
        raise ReturnNotAllowed(f"Return is {ret.status}")
    order = await orders.get_for_update(db, ret.order_id)
    payment = await payments.payment_for_order(db, order.id)
    ret.status, ret.restocked = ReturnStatus.RECEIVED, restock
    ret.admin_note = note or ret.admin_note
    orders.record_transition(db, order, OrderStatus.RETURNED, note="Return received", actor_id=actor_id)
    if restock:
        await _restock(db, order, actor_id, "returned")
    await payments.create_refund(
        db, pay, order, payment, None, "Order returned", key=f"return:{ret.id}", actor_id=actor_id
    )
    await db.commit()
    return ret


async def list_returns(db: AsyncSession, status: ReturnStatus | None, limit: int) -> list[OrderReturn]:
    stmt = select(OrderReturn)
    if status:
        stmt = stmt.where(OrderReturn.status == status)
    return list(await db.scalars(stmt.order_by(OrderReturn.created_at.desc()).limit(limit)))


# ---------- Staff views ----------


async def admin_order(db: AsyncSession, order_id: uuid.UUID) -> AdminOrderOut:
    order = await db.scalar(
        select(Order).where(Order.id == order_id).execution_options(populate_existing=True)
    )
    if order is None:
        raise orders.OrderNotFound()
    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id))
    refunds = await db.scalars(select(Refund).where(Refund.order_id == order.id).order_by(Refund.created_at))
    returns = await db.scalars(
        select(OrderReturn).where(OrderReturn.order_id == order.id).order_by(OrderReturn.created_at)
    )
    out = AdminOrderOut.model_validate(order)
    out.payment = PaymentSummary.model_validate(payment) if payment else None
    out.refunds = [AdminRefundOut.model_validate(r) for r in refunds]
    out.shipments = [
        AdminShipmentOut.model_validate(s) for s in await shipping.shipments_for_order(db, order.id)
    ]
    out.returns = [ReturnOut.model_validate(r) for r in returns]
    return out


async def admin_list(
    db: AsyncSession, status: OrderStatus | None, q: str | None, cursor: str | None, limit: int
) -> Page[AdminOrderRow]:
    stmt = select(Order)
    if status:
        stmt = stmt.where(Order.status == status)
    if q:
        q = q.strip()
        stmt = stmt.where((Order.number == q.upper()) | (Order.customer_email == q.lower()))
    if cursor:
        ts, oid = decode_cursor(cursor, 2)
        stmt = stmt.where(tuple_(Order.created_at, Order.id) < (datetime.fromisoformat(ts), uuid.UUID(oid)))
    rows = list(await db.scalars(stmt.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1)))
    items = [AdminOrderRow.model_validate(o) for o in rows[:limit]]
    return Page(
        items=items,
        next_cursor=encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None,
    )


async def start_processing(db: AsyncSession, order_id: uuid.UUID, actor_id: uuid.UUID) -> Order:
    order = await orders.get_for_update(db, order_id)
    orders.record_transition(db, order, OrderStatus.PROCESSING, note="Fulfilment started", actor_id=actor_id)
    await db.commit()
    return order
