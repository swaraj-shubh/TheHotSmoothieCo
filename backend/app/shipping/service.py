import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError, NotFound
from app.orders import service as orders
from app.orders.models import Order, OrderStatus
from app.orders.schemas import OrderOut
from app.shipping.models import Shipment, ShipmentTrackingEvent
from app.shipping.provider import (
    ACTIVE_SHIPMENT_STATUSES,
    Package,
    ShipmentStatus,
    ShippingProvider,
    ShippingProviderError,
    TrackingUpdate,
)

log = structlog.get_logger()

TERMINAL = {ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED, ShipmentStatus.RTO}
CANCELLABLE = {ShipmentStatus.CREATED, ShipmentStatus.AWB_ASSIGNED, ShipmentStatus.PICKUP_SCHEDULED}
# Courier status -> order status it implies (forward shipments only).
ORDER_STATUS_FOR = {
    ShipmentStatus.IN_TRANSIT: OrderStatus.SHIPPED,
    ShipmentStatus.OUT_FOR_DELIVERY: OrderStatus.OUT_FOR_DELIVERY,
    ShipmentStatus.DELIVERED: OrderStatus.DELIVERED,
}


class ShipmentNotFound(NotFound):
    code, message = "SHIPMENT_NOT_FOUND", "Shipment not found"


class CannotShip(AppError):
    code, message = "CANNOT_SHIP", "This order cannot be shipped right now"


def package_for(order: Order) -> Package:
    s = get_settings()
    weight = sum((i.weight_grams or s.default_item_weight_grams) * i.quantity for i in order.items)
    length, breadth, height = s.default_package_cm
    return Package(max(weight, 50), length, breadth, height)


def snapshot(order: Order) -> dict:
    return OrderOut.model_validate(order).model_dump(mode="json") | {"customer_email": order.customer_email}


async def active_forward_shipment(db: AsyncSession, order_id: uuid.UUID) -> Shipment | None:
    return await db.scalar(
        select(Shipment).where(
            Shipment.order_id == order_id,
            Shipment.is_return.is_(False),
            Shipment.status != ShipmentStatus.CANCELLED,
        )
    )


async def _assign_awb(db: AsyncSession, provider: ShippingProvider, shipment: Shipment, order: Order) -> None:
    awb = await provider.assign_awb(shipment.provider_shipment_id)
    shipment.awb, shipment.courier = awb.awb, awb.courier
    shipment.status = ShipmentStatus.AWB_ASSIGNED
    try:
        shipment.label_url = await provider.label(shipment.provider_shipment_id)
    except ShippingProviderError:
        log.warning("label_generation_failed", shipment_id=str(shipment.id))  # can be regenerated later
    if not shipment.is_return:
        orders.advance(db, order, OrderStatus.PACKED, note=f"Packed; {awb.courier} AWB {awb.awb}")


async def create_shipment(
    db: AsyncSession, provider: ShippingProvider, order_id: uuid.UUID, actor_id: uuid.UUID | None
) -> Shipment:
    order = await orders.get_for_update(db, order_id)
    if order.status not in (OrderStatus.CONFIRMED, OrderStatus.PROCESSING):
        raise CannotShip(f"Order is {order.status}")
    if await active_forward_shipment(db, order.id):
        raise CannotShip("This order already has a shipment")

    package = package_for(order)
    created = await provider.create_shipment(snapshot(order), package)
    shipment = Shipment(
        order_id=order.id,
        provider=provider.name,
        provider_order_id=created.provider_order_id,
        provider_shipment_id=created.provider_shipment_id,
        status=ShipmentStatus.CREATED,
        weight_grams=package.weight_grams,
        is_return=False,
        events=[],
    )
    db.add(shipment)
    orders.advance(db, order, OrderStatus.PROCESSING, note="Fulfilment started", actor_id=actor_id)
    await db.flush()
    try:
        await _assign_awb(db, provider, shipment, order)
    except ShippingProviderError:
        # The provider has the shipment; keep it so AWB assignment can be retried instead of duplicated.
        log.warning("awb_assignment_failed", shipment_id=str(shipment.id))
    await db.commit()
    return shipment


async def get_shipment(db: AsyncSession, shipment_id: uuid.UUID) -> Shipment:
    shipment = await db.scalar(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if shipment is None:
        raise ShipmentNotFound()
    return shipment


async def retry_awb(db: AsyncSession, provider: ShippingProvider, shipment_id: uuid.UUID) -> Shipment:
    shipment = await get_shipment(db, shipment_id)
    if shipment.status != ShipmentStatus.CREATED:
        raise CannotShip("AWB already assigned")
    order = await orders.get_for_update(db, shipment.order_id)
    await _assign_awb(db, provider, shipment, order)
    await db.commit()
    return shipment


async def cancel_shipment(db: AsyncSession, provider: ShippingProvider, shipment: Shipment) -> None:
    if ShipmentStatus(shipment.status) not in CANCELLABLE:
        raise CannotShip("The parcel is already with the courier and can't be cancelled")
    await provider.cancel(shipment.provider_order_id)
    shipment.status = ShipmentStatus.CANCELLED


async def apply_update(db: AsyncSession, shipment: Shipment, update: TrackingUpdate) -> None:
    """Idempotent: events are de-duplicated by the DB; terminal statuses never regress."""
    for e in update.events:
        await db.execute(
            insert(ShipmentTrackingEvent)
            .values(
                id=uuid.uuid4(),
                shipment_id=shipment.id,
                status=e.status,
                raw_status=e.raw_status[:255],
                location=(e.location or "")[:255] or None,
                description=(e.description or "")[:500] or None,
                occurred_at=e.occurred_at,
            )
            .on_conflict_do_nothing(constraint="uq_tracking_event")
        )
    shipment.last_synced_at = datetime.now(UTC)
    if ShipmentStatus(shipment.status) in TERMINAL or update.status in (ShipmentStatus.CREATED,):
        return
    shipment.status, shipment.raw_status = update.status, update.raw_status[:120]
    if update.status == ShipmentStatus.DELIVERED:
        shipment.delivered_at = datetime.now(UTC)
    if shipment.is_return:
        return  # return parcels are closed out by staff on receipt (inspection, restock)

    order = await orders.get_for_update(db, shipment.order_id)
    if target := ORDER_STATUS_FOR.get(update.status):
        orders.advance(db, order, target, note=f"Courier: {update.raw_status}")
    elif update.status == ShipmentStatus.RTO and order.status in (
        OrderStatus.SHIPPED,
        OrderStatus.OUT_FOR_DELIVERY,
    ):
        orders.record_transition(db, order, OrderStatus.RETURNED, note="Returned to origin by courier")
        log.warning("shipment_rto", order_id=str(order.id))  # staff decide on refund/reship


async def handle_webhook(db: AsyncSession, provider: ShippingProvider, payload: dict) -> bool:
    update = provider.parse_webhook(payload)
    shipment = await db.scalar(select(Shipment).where(Shipment.awb == update.awb).with_for_update())
    if shipment is None:
        log.warning("tracking_for_unknown_awb", awb=update.awb)
        return False
    await apply_update(db, shipment, update)
    return True


async def sync_active(db: AsyncSession, provider: ShippingProvider, limit: int = 50) -> int:
    """Polling fallback for missed webhooks (run by the worker)."""
    shipments = list(
        await db.scalars(
            select(Shipment)
            .where(Shipment.status.in_(ACTIVE_SHIPMENT_STATUSES), Shipment.awb.is_not(None))
            .order_by(Shipment.last_synced_at.asc().nulls_first())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    )
    for shipment in shipments:
        try:
            await apply_update(db, shipment, await provider.track(shipment.awb or ""))
        except ShippingProviderError:
            log.warning("tracking_sync_failed", shipment_id=str(shipment.id))
    await db.commit()
    return len(shipments)


async def shipments_for_order(db: AsyncSession, order_id: uuid.UUID) -> list[Shipment]:
    return list(
        await db.scalars(
            select(Shipment)
            .where(Shipment.order_id == order_id)
            .order_by(Shipment.created_at)
            .execution_options(populate_existing=True)
        )
    )
