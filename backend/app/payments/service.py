"""Payment state machine.

Payment truth comes only from the gateway: either a verified webhook, or the client callback
whose signature we verify *and* whose payment we re-fetch from the gateway. Both paths funnel
into the same idempotent handlers (on_captured / on_failed / on_refund_update), so duplicate,
late or out-of-order events can never confirm twice, refund twice, or move stock twice.

Handlers don't commit; the caller (API endpoint / webhook processor) owns the transaction.
"""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cart import service as cart_service
from app.core.exceptions import AppError, Conflict, NotFound
from app.inventory import service as inventory
from app.notifications import service as notifications
from app.notifications.templates import rupees
from app.orders import service as orders
from app.orders.models import TRANSITIONS, Order, OrderStatus
from app.payments.models import Payment, PaymentStatus, Refund, RefundStatus
from app.payments.provider import PaymentProvider, PaymentProviderError, ProviderPayment, ProviderRefund
from app.payments.schemas import InitiateOut, PaymentStatusOut, Prefill, VerifyIn
from app.users.models import User

log = structlog.get_logger()


class OrderNotPayable(Conflict):
    code, message = "ORDER_NOT_PAYABLE", "This order can no longer be paid"


class InvalidPaymentSignature(AppError):
    code, message = "INVALID_PAYMENT_SIGNATURE", "Payment could not be verified"


class PaymentNotFound(NotFound):
    code, message = "PAYMENT_NOT_FOUND", "No payment found for this order"


class RefundNotAllowed(AppError):
    code, message = "REFUND_NOT_ALLOWED", "This refund is not allowed"


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- Customer flow ----------


async def initiate(
    db: AsyncSession, provider: PaymentProvider, user: User, order_id: uuid.UUID
) -> InitiateOut:
    order = await orders.get_for_update(db, order_id, user.id)
    if order.status != OrderStatus.PENDING_PAYMENT or (
        order.payment_due_at and order.payment_due_at < _now()
    ):
        raise OrderNotPayable()
    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id))
    if payment is None:  # idempotent: re-initiating reuses the same gateway order
        gw = await provider.create_order(
            order.total_paise, order.currency, receipt=order.number, notes={"order_id": str(order.id)}
        )
        payment = Payment(
            order_id=order.id,
            provider=provider.name,
            provider_order_id=gw.id,
            amount_paise=gw.amount_paise,
            currency=gw.currency,
            status=PaymentStatus.CREATED,
        )
        db.add(payment)
        await db.commit()
    return InitiateOut(
        provider=payment.provider,
        public_key=provider.public_key,
        provider_order_id=payment.provider_order_id,
        amount_paise=payment.amount_paise,
        currency=payment.currency,
        order_id=order.id,
        order_number=order.number,
        payment_due_at=order.payment_due_at,
        prefill=Prefill(name=order.customer_name, email=order.customer_email, contact=order.customer_phone),
    )


async def verify_client(
    db: AsyncSession, provider: PaymentProvider, user: User, order_id: uuid.UUID, data: VerifyIn
) -> PaymentStatusOut:
    """The browser's "payment done" callback. Never trusted on its own: signature checked, then the
    payment is re-fetched from the gateway and handled exactly like a webhook."""
    order = await orders.get_for_user(db, order_id, user.id)
    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id))
    if (
        payment is None
        or payment.provider_order_id != data.provider_order_id
        or not provider.verify_checkout_signature(
            data.provider_order_id, data.provider_payment_id, data.signature
        )
    ):
        log.warning("payment_signature_invalid", order_id=str(order_id), user_id=str(user.id))
        raise InvalidPaymentSignature()

    gw = await provider.fetch_payment(data.provider_payment_id)
    if gw.order_id != payment.provider_order_id:
        raise InvalidPaymentSignature()
    await apply_payment(db, provider, gw)
    await db.commit()
    return await status(db, user, order_id)


async def simulate_dev_payment(
    db: AsyncSession, provider, user: User, order_id: uuid.UUID, success: bool
) -> PaymentStatusOut:
    order = await orders.get_for_user(db, order_id, user.id)
    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id))
    if payment is None:
        raise PaymentNotFound()
    await apply_payment(db, provider, provider.payment_for(payment.provider_order_id, success))
    await db.commit()
    return await status(db, user, order_id)


async def status(db: AsyncSession, user: User, order_id: uuid.UUID) -> PaymentStatusOut:
    order = await orders.get_for_user(db, order_id, user.id)
    payment = await db.scalar(select(Payment).where(Payment.order_id == order.id))
    return PaymentStatusOut(
        order_id=order.id, order_status=order.status, payment_status=payment.status if payment else None
    )


# ---------- Event handlers (webhook + client callback) ----------


async def apply_payment(db: AsyncSession, provider: PaymentProvider, gw: ProviderPayment) -> bool:
    """Route a gateway payment snapshot to its handler. Returns False if it isn't one of ours."""
    payment = await db.scalar(
        select(Payment)
        .where(Payment.provider == provider.name, Payment.provider_order_id == gw.order_id)
        .with_for_update()
    )
    if payment is None:
        log.warning("payment_for_unknown_order", provider_order_id=gw.order_id, payment_id=gw.id)
        return False
    if gw.status == "captured":
        await _on_captured(db, provider, payment, gw)
    elif gw.status == "authorized":
        await _on_authorized(db, payment, gw)
    elif gw.status == "failed":
        await _on_failed(db, payment, gw)
    return True


async def _on_captured(
    db: AsyncSession, provider: PaymentProvider, payment: Payment, gw: ProviderPayment
) -> None:
    order = await orders.get_for_update(db, payment.order_id)

    if payment.status == PaymentStatus.CAPTURED:
        if payment.provider_payment_id == gw.id:
            return  # duplicate event: already handled
        # A *second* successful payment for the same order (e.g. customer paid twice): give it back.
        log.error("duplicate_capture", order_id=str(order.id), payment_id=gw.id)
        await create_refund(
            db,
            provider,
            order,
            payment,
            gw.amount_paise,
            "Duplicate payment",
            key=f"duplicate:{gw.id}",
            provider_payment_id=gw.id,
        )
        return

    if gw.amount_paise != payment.amount_paise:
        log.error(
            "capture_amount_mismatch",
            order_id=str(order.id),
            expected=payment.amount_paise,
            got=gw.amount_paise,
        )
        await create_refund(
            db,
            provider,
            order,
            payment,
            gw.amount_paise,
            "Amount mismatch",
            key=f"mismatch:{gw.id}",
            provider_payment_id=gw.id,
        )
        return

    payment.status = PaymentStatus.CAPTURED
    payment.provider_payment_id = gw.id
    payment.method = gw.method
    payment.captured_at = _now()

    if order.status in (OrderStatus.PENDING_PAYMENT, OrderStatus.PAYMENT_PROCESSING):
        await inventory.commit_reservation(db, order.id)
        orders.record_transition(
            db, order, OrderStatus.CONFIRMED, note=f"Payment captured ({gw.method or 'online'})"
        )
        await cart_service.clear_after_order(db, order.user_id, [i.variant_id for i in order.items])
        log.info("order_confirmed", order_id=str(order.id), number=order.number)
    else:
        # Money arrived after the order was cancelled/expired and its stock released: refund in full
        # rather than ship something we may no longer have.
        log.warning("late_payment_refunded", order_id=str(order.id), status=order.status)
        await create_refund(
            db,
            provider,
            order,
            payment,
            payment.amount_paise,
            "Payment received after order was cancelled",
            key=f"late:{gw.id}",
        )
    await db.flush()


async def _on_authorized(db: AsyncSession, payment: Payment, gw: ProviderPayment) -> None:
    if payment.status != PaymentStatus.CREATED:
        return
    payment.status = PaymentStatus.AUTHORIZED
    payment.provider_payment_id = gw.id
    order = await orders.get_for_update(db, payment.order_id)
    if order.status == OrderStatus.PENDING_PAYMENT:
        # Stops the expiry sweep cancelling an order whose money is on its way.
        # ponytail: a capture that never arrives leaves this stuck; the Phase 5 reconciliation job
        # re-fetches PAYMENT_PROCESSING orders older than a day.
        orders.record_transition(db, order, OrderStatus.PAYMENT_PROCESSING, note="Payment authorised")


async def _on_failed(db: AsyncSession, payment: Payment, gw: ProviderPayment) -> None:
    if payment.status == PaymentStatus.CAPTURED:
        return  # an older failed attempt reported after success: irrelevant
    payment.failed_attempts += 1
    payment.last_error_code = gw.error_code
    payment.last_error_description = (gw.error_description or "")[:500] or None
    order = await orders.get_for_update(db, payment.order_id)
    if order.status == OrderStatus.PAYMENT_PROCESSING:
        await orders.void_unpaid(db, order, OrderStatus.FAILED, "Payment failed after authorisation")
    # PENDING_PAYMENT stays pending: the customer can retry until the payment window closes.


# ---------- Refunds ----------


async def _refunded_or_pending(db: AsyncSession, provider_payment_id: str) -> int:
    return (
        await db.scalar(
            select(func.coalesce(func.sum(Refund.amount_paise), 0)).where(
                Refund.provider_payment_id == provider_payment_id, Refund.status != RefundStatus.FAILED
            )
        )
        or 0
    )


async def refundable_paise(db: AsyncSession, payment: Payment) -> int:
    if payment.status != PaymentStatus.CAPTURED or not payment.provider_payment_id:
        return 0
    return payment.amount_paise - await _refunded_or_pending(db, payment.provider_payment_id)


async def create_refund(
    db: AsyncSession,
    provider: PaymentProvider,
    order: Order,
    payment: Payment,
    amount_paise: int | None,
    reason: str,
    *,
    key: str,
    actor_id: uuid.UUID | None = None,
    provider_payment_id: str | None = None,
) -> Refund:
    """Idempotent by `key`. Caller holds the order lock. `provider_payment_id` targets a stray
    (duplicate/mismatched) capture instead of the order's own payment."""
    if existing := await db.scalar(select(Refund).where(Refund.idempotency_key == key)):
        return existing

    stray = provider_payment_id is not None and provider_payment_id != payment.provider_payment_id
    target = provider_payment_id or payment.provider_payment_id
    if not target:
        raise RefundNotAllowed("Nothing has been paid on this order")
    if stray:
        assert amount_paise is not None
        remaining = amount_paise - await _refunded_or_pending(db, target)
    else:
        remaining = await refundable_paise(db, payment)
    amount = remaining if amount_paise is None else amount_paise
    if amount <= 0 or amount > remaining:
        raise RefundNotAllowed(f"Refundable amount is ₹{remaining / 100:.2f}")

    refund = Refund(
        order_id=order.id,
        payment_id=payment.id,
        provider_payment_id=target,
        amount_paise=amount,
        status=RefundStatus.PENDING,
        reason=reason,
        idempotency_key=key,
        created_by=actor_id,
    )
    db.add(refund)
    await db.flush()  # unique key claimed before calling the gateway
    try:
        gw = await provider.refund(target, amount, notes={"refund_id": str(refund.id), "order": order.number})
        refund.provider_refund_id = gw.id
        await _apply_refund_status(db, order, refund, gw.status)
    except PaymentProviderError as exc:
        if exc.ambiguous:
            # The gateway may have processed it: stay PENDING (still counted against the refundable
            # amount) and let the refund webhook — matched via notes.refund_id — settle it.
            refund.failure_reason = "Gateway did not respond; awaiting confirmation"
        else:
            refund.status = RefundStatus.FAILED
            refund.failure_reason = "Rejected by payment gateway"
        log.error("refund_gateway_error", refund_id=str(refund.id), ambiguous=exc.ambiguous)

    if not stray:
        await _sync_order_refund_state(db, order, payment)
    await db.flush()
    log.info(
        "refund_created",
        refund_id=str(refund.id),
        order_id=str(order.id),
        amount=amount,
        status=refund.status,
    )
    return refund


async def _apply_refund_status(db: AsyncSession, order: Order, refund: Refund, gw_status: str) -> None:
    if refund.status != RefundStatus.PENDING:
        return  # terminal states never change
    if gw_status == "processed":
        refund.status = RefundStatus.PROCESSED
        refund.processed_at = _now()
        refund.failure_reason = None
        await notifications.enqueue(
            db,
            "refund_processed",
            recipient=order.customer_email,
            user_id=order.user_id,
            context=notifications.order_context(order) | {"amount": rupees(refund.amount_paise)},
            dedupe_key=f"refund_processed:{refund.id}",
        )
    elif gw_status == "failed":
        refund.status = RefundStatus.FAILED
        refund.failure_reason = "Refund failed at the gateway"


async def _sync_order_refund_state(db: AsyncSession, order: Order, payment: Payment) -> None:
    """Full refund requested -> REFUND_PENDING; fully processed -> REFUNDED. Partial refunds
    don't change the order status."""
    if not payment.provider_payment_id:
        return
    rows = list(
        await db.scalars(select(Refund).where(Refund.provider_payment_id == payment.provider_payment_id))
    )
    active = sum(r.amount_paise for r in rows if r.status != RefundStatus.FAILED)
    processed = sum(r.amount_paise for r in rows if r.status == RefundStatus.PROCESSED)
    status = OrderStatus(order.status)
    if (
        active >= payment.amount_paise
        and status != OrderStatus.REFUND_PENDING
        and OrderStatus.REFUND_PENDING in TRANSITIONS[status]
    ):
        orders.record_transition(db, order, OrderStatus.REFUND_PENDING, note="Full refund initiated")
    if OrderStatus(order.status) == OrderStatus.REFUND_PENDING and processed >= payment.amount_paise:
        orders.record_transition(db, order, OrderStatus.REFUNDED, note="Refund completed")


async def on_refund_update(db: AsyncSession, gw: ProviderRefund) -> bool:
    refund = await db.scalar(select(Refund).where(Refund.provider_refund_id == gw.id).with_for_update())
    if refund is None and (local_id := gw.notes.get("refund_id")):
        # Our earlier gateway call timed out before we learned the refund id.
        try:
            refund = await db.scalar(select(Refund).where(Refund.id == uuid.UUID(local_id)).with_for_update())
        except ValueError:
            refund = None
        if refund:
            refund.provider_refund_id = gw.id
    if refund is None:
        log.warning("refund_event_for_unknown_refund", provider_refund_id=gw.id)
        return False
    order = await orders.get_for_update(db, refund.order_id)
    await _apply_refund_status(db, order, refund, gw.status)
    payment = await db.get(Payment, refund.payment_id)
    assert payment is not None
    if refund.provider_payment_id == payment.provider_payment_id:
        await _sync_order_refund_state(db, order, payment)
    return True


async def payment_for_order(db: AsyncSession, order_id: uuid.UUID) -> Payment:
    payment = await db.scalar(select(Payment).where(Payment.order_id == order_id).with_for_update())
    if payment is None:
        raise PaymentNotFound()
    return payment


async def reconcile_processing(db: AsyncSession, provider: PaymentProvider, limit: int = 50) -> int:
    """Orders stuck in PAYMENT_PROCESSING (authorised, capture webhook never arrived): ask the
    gateway. Still not captured after 7 days -> the bank has auto-reversed it; fail the order."""
    stale = list(
        await db.scalars(
            select(Order.id)
            .where(
                Order.status == OrderStatus.PAYMENT_PROCESSING, Order.updated_at < _now() - timedelta(hours=1)
            )
            .limit(limit)
        )
    )
    for order_id in stale:
        payment = await db.scalar(select(Payment).where(Payment.order_id == order_id))
        if payment and payment.provider_payment_id:
            try:
                await apply_payment(db, provider, await provider.fetch_payment(payment.provider_payment_id))
            except PaymentProviderError:
                log.warning("reconcile_fetch_failed", order_id=str(order_id))
        order = await orders.get_for_update(db, order_id)
        if order.status == OrderStatus.PAYMENT_PROCESSING and order.created_at < _now() - timedelta(days=7):
            await orders.void_unpaid(db, order, OrderStatus.FAILED, "Payment never captured")
        await db.commit()
    return len(stale)
