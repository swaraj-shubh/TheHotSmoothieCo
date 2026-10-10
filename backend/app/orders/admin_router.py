import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.auth.dependencies import DB, require_roles
from app.checkout.service import IdempotencyKey
from app.core.pagination import MAX_LIMIT, Page
from app.core.ratelimit import rate_limit
from app.orders import lifecycle
from app.orders.models import OrderStatus, ReturnStatus
from app.orders.schemas import (
    AdminCancelIn,
    AdminOrderOut,
    AdminOrderRow,
    AdminRefundOut,
    AdminShipmentOut,
    ApproveReturnIn,
    ReceiveReturnIn,
    RejectReturnIn,
    ReturnOut,
)
from app.payments.provider import PaymentProvider, get_payment_provider, optional_payment_provider
from app.payments.schemas import RefundIn
from app.shipping import service as shipping
from app.shipping.provider import ShippingProvider, get_shipping_provider, optional_shipping_provider
from app.users.models import RoleName, User

router = APIRouter(
    prefix="/admin", tags=["admin: orders"], dependencies=[Depends(rate_limit("admin", 300, 60))]
)
OrderStaff = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.ORDER_MANAGER))]
# Support can look but not act.
OrderViewer = Annotated[
    User, Depends(require_roles(RoleName.ADMIN, RoleName.ORDER_MANAGER, RoleName.CUSTOMER_SUPPORT))
]
Pay = Annotated[PaymentProvider, Depends(get_payment_provider)]
Ship = Annotated[ShippingProvider, Depends(get_shipping_provider)]


@router.get("/orders", response_model=Page[AdminOrderRow])
async def list_orders(
    _: OrderViewer,
    db: DB,
    status: OrderStatus | None = None,
    q: Annotated[str | None, Query(max_length=320, description="order number or customer email")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await lifecycle.admin_list(db, status, q, cursor, limit)


@router.get("/orders/{order_id}", response_model=AdminOrderOut)
async def get_order(order_id: uuid.UUID, _: OrderViewer, db: DB):
    return await lifecycle.admin_order(db, order_id)


@router.post("/orders/{order_id}/process", response_model=AdminOrderOut)
async def start_processing(order_id: uuid.UUID, user: OrderStaff, db: DB):
    await lifecycle.start_processing(db, order_id, user.id)
    return await lifecycle.admin_order(db, order_id)


@router.post("/orders/{order_id}/cancel", response_model=AdminOrderOut)
async def cancel(
    order_id: uuid.UUID,
    data: AdminCancelIn,
    user: OrderStaff,
    db: DB,
    pay: Annotated[PaymentProvider | None, Depends(optional_payment_provider)],
    ship: Annotated[ShippingProvider | None, Depends(optional_shipping_provider)],
):
    """Cancels at any pre-dispatch stage: cancels the courier booking, restocks, refunds in full."""
    await lifecycle.cancel(
        db, order_id, reason=data.reason, pay=pay, ship=ship, actor_id=user.id, restock=data.restock
    )
    return await lifecycle.admin_order(db, order_id)


@router.post("/orders/{order_id}/refunds", response_model=AdminRefundOut)
async def refund(
    order_id: uuid.UUID,
    data: RefundIn,
    user: OrderStaff,
    db: DB,
    pay: Pay,
    idempotency_key: Annotated[IdempotencyKey, Header(alias="Idempotency-Key")],
):
    """Partial or full refund. Reusing an Idempotency-Key returns the original refund, never a second one."""
    return await lifecycle.staff_refund(
        db, pay, order_id, data.amount_paise, data.reason, idempotency_key, user.id
    )


@router.post("/orders/{order_id}/shipments", response_model=AdminShipmentOut)
async def create_shipment(order_id: uuid.UUID, user: OrderStaff, db: DB, ship: Ship):
    """Books the courier, assigns an AWB and generates the label. If AWB assignment fails the
    shipment is kept (status CREATED) — retry with /shipments/{id}/awb rather than re-booking."""
    s = await shipping.create_shipment(db, ship, order_id, user.id)
    return await shipping.get_shipment(db, s.id)


@router.post("/shipments/{shipment_id}/awb", response_model=AdminShipmentOut)
async def retry_awb(shipment_id: uuid.UUID, _: OrderStaff, db: DB, ship: Ship):
    await shipping.retry_awb(db, ship, shipment_id)
    return await shipping.get_shipment(db, shipment_id)


@router.post("/shipments/{shipment_id}/sync", response_model=AdminShipmentOut)
async def sync_tracking(shipment_id: uuid.UUID, _: OrderStaff, db: DB, ship: Ship):
    shipment = await shipping.get_shipment(db, shipment_id)
    if shipment.awb:
        await shipping.apply_update(db, shipment, await ship.track(shipment.awb))
        await db.commit()
    return await shipping.get_shipment(db, shipment_id)


@router.get("/returns", response_model=list[ReturnOut])
async def list_returns(
    _: OrderViewer,
    db: DB,
    status: ReturnStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await lifecycle.list_returns(db, status, limit)


@router.post("/returns/{return_id}/approve", response_model=ReturnOut)
async def approve_return(
    return_id: uuid.UUID,
    data: ApproveReturnIn,
    _: OrderStaff,
    db: DB,
    ship: Annotated[ShippingProvider | None, Depends(optional_shipping_provider)],
):
    return await lifecycle.approve_return(db, return_id, ship, data.schedule_pickup, data.note)


@router.post("/returns/{return_id}/reject", response_model=ReturnOut)
async def reject_return(return_id: uuid.UUID, data: RejectReturnIn, user: OrderStaff, db: DB):
    return await lifecycle.reject_return(db, return_id, data.note, user.id)


@router.post("/returns/{return_id}/receive", response_model=ReturnOut)
async def receive_return(return_id: uuid.UUID, data: ReceiveReturnIn, user: OrderStaff, db: DB, pay: Pay):
    """Parcel is back: closes the return, optionally restocks, refunds in full."""
    return await lifecycle.receive_return(db, pay, return_id, data.restock, data.note, user.id)
