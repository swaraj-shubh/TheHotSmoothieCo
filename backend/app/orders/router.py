import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from fastapi.params import Depends

from app.auth.dependencies import DB, CurrentUser
from app.core.pagination import MAX_LIMIT, Page
from app.orders import lifecycle, service
from app.orders.schemas import OrderOut, OrderSummary, ReturnIn, ReturnOut
from app.payments.provider import PaymentProvider, optional_payment_provider
from app.shipping.provider import ShippingProvider, optional_shipping_provider

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=Page[OrderSummary])
async def my_orders(
    user: CurrentUser,
    db: DB,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 20,
):
    return await service.list_for_user(db, user.id, cursor, limit)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: uuid.UUID, user: CurrentUser, db: DB):
    return await service.get_for_user(db, order_id, user.id)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel(
    order_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    pay: Annotated[PaymentProvider | None, Depends(optional_payment_provider)],
    ship: Annotated[ShippingProvider | None, Depends(optional_shipping_provider)],
):
    """Unpaid: cancelled immediately. Paid but not yet dispatched: cancelled and refunded in full."""
    await lifecycle.cancel(db, order_id, reason="Cancelled by customer", pay=pay, ship=ship, user_id=user.id)
    return await service.get_for_user(db, order_id, user.id)


@router.post("/{order_id}/return", response_model=ReturnOut, status_code=status.HTTP_201_CREATED)
async def request_return(order_id: uuid.UUID, data: ReturnIn, user: CurrentUser, db: DB):
    return await lifecycle.request_return(db, user.id, order_id, data.reason)
