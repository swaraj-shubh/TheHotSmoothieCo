"""Checkout: cart -> PENDING_PAYMENT order, in ONE database transaction.

    validate cart lines (live catalog prices & availability)
    -> validate coupon -> compute totals server-side
    -> create order with snapshots -> reserve stock -> claim coupon -> commit

Any failure rolls back everything: no orphan order, no held stock, no burnt coupon.
The client's Idempotency-Key makes double-clicks and network retries return the same order.
Payment is initiated against the returned order (Phase 4).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import structlog
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.cart import service as cart_service
from app.catalog import repository as catalog
from app.core.config import get_settings
from app.core.exceptions import AppError, Conflict
from app.coupons import service as coupons
from app.inventory import service as inventory
from app.orders import service as orders
from app.orders.models import Order, OrderItem, OrderStatus
from app.users.models import Address, User
from app.users.service import get_address

log = structlog.get_logger()

IdempotencyKey = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{8,80}$")]


MIN_CHARGE_PAISE = 100  # gateways can't charge less than ₹1


class CheckoutIn(BaseModel):
    shipping_address_id: uuid.UUID
    billing_address_id: uuid.UUID | None = None  # defaults to shipping
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    # What the customer saw. If the server total differs (price changed meanwhile) we refuse
    # rather than charge an amount they didn't agree to.
    expected_total_paise: int | None = Field(None, ge=0)


class CartNotReady(AppError):
    code, message = "CART_NOT_READY", "Some items in your cart need attention before checkout"


class PriceChanged(Conflict):
    code, message = "PRICE_CHANGED", "Prices changed since you last viewed your cart; please review"


def _address_snapshot(a: Address) -> dict:
    return {
        k: getattr(a, k)
        for k in (
            "full_name",
            "phone",
            "line1",
            "line2",
            "landmark",
            "city",
            "state",
            "postal_code",
            "country",
        )
    }


async def _existing(db: AsyncSession, user_id: uuid.UUID, key: str) -> Order | None:
    return await db.scalar(
        select(Order)
        .where(Order.user_id == user_id, Order.idempotency_key == key)
        .execution_options(populate_existing=True)
    )


async def place_order(
    db: AsyncSession, user: User, data: CheckoutIn, idempotency_key: str
) -> tuple[Order, bool]:
    """Returns (order, created). created=False means this key was already used: same order back."""
    if existing := await _existing(db, user.id, idempotency_key):
        return existing, False

    s = get_settings()
    cart, _ = await cart_service.get_cart(db, user.id, None)
    if cart is None or not cart.items:
        raise CartNotReady("Your cart is empty")

    view, lines = await cart_service.build_lines(db, cart.items)
    if problems := [{"variant_id": str(i.variant_id), "issue": i.issue} for i in view if i.issue]:
        raise CartNotReady(details=problems)

    coupon, terms = None, None
    if cart.coupon_code:
        coupon, terms = await coupons.validate(db, cart.coupon_code, user.id, lines)
    totals = cart_service.totals(lines, terms)
    if totals.total_paise < MIN_CHARGE_PAISE:
        raise AppError("The order total must be at least ₹1", code="ORDER_TOTAL_TOO_LOW")
    if data.expected_total_paise is not None and data.expected_total_paise != totals.total_paise:
        raise PriceChanged(details={"total_paise": totals.total_paise})

    shipping = await get_address(db, user.id, data.shipping_address_id)
    billing = await get_address(db, user.id, data.billing_address_id) if data.billing_address_id else shipping

    order = Order(
        id=uuid.uuid4(),  # needed before flush: the status-history row references it
        number=orders.new_order_number(),
        user_id=user.id,
        subtotal_paise=totals.subtotal_paise,
        discount_paise=totals.discount_paise,
        shipping_paise=totals.shipping_paise,
        tax_paise=totals.tax_paise,
        total_paise=totals.total_paise,
        prices_include_tax=s.prices_include_tax,
        coupon_id=coupon.id if coupon else None,
        coupon_code=coupon.code if coupon else None,
        customer_email=user.email,
        customer_name=user.full_name,
        customer_phone=shipping.phone,
        shipping_address=_address_snapshot(shipping),
        billing_address=_address_snapshot(billing),
        notes=data.notes,
        idempotency_key=idempotency_key,
        payment_due_at=datetime.now(UTC) + timedelta(seconds=s.inventory_hold_seconds),
        items=[],
        history=[],
    )
    orders.record_transition(db, order, OrderStatus.PENDING_PAYMENT, note="Order placed")
    db.add(order)
    try:
        # Flush now so a concurrent request with the same key fails here, before any stock work.
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        if "uq_orders_user_idempotency_key" in str(exc.orig) and (
            again := await _existing(db, user.id, idempotency_key)
        ):
            return again, False
        raise

    info = await catalog.purchasables(db, [line.variant_id for line in lines])
    for line in lines:
        p = info[line.variant_id]
        discount = totals.line_discounts.get(line.variant_id, 0)
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=p.product_id,
                variant_id=p.variant_id,
                sku=p.sku,
                product_title=p.product_title,
                variant_title=p.variant_title,
                attributes=p.attributes,
                image_url=p.image_url,
                weight_grams=p.weight_grams,
                unit_price_paise=line.unit_price_paise,
                quantity=line.quantity,
                discount_paise=discount,
                line_total_paise=line.total - discount,
            )
        )

    # The authoritative stock check: atomic, all-or-nothing (see inventory.service).
    await inventory.reserve(
        db, order.id, {ln.variant_id: ln.quantity for ln in lines}, s.inventory_hold_seconds
    )
    if coupon:
        await coupons.claim(db, coupon, user.id, order.id, totals.discount_paise)

    await db.commit()
    log.info("order_placed", order_id=str(order.id), number=order.number, total_paise=order.total_paise)
    return await orders.get_for_user(db, order.id, user.id), True
