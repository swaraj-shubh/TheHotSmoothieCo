from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status

from app.auth.dependencies import DB, CurrentUser
from app.checkout import service
from app.checkout.service import CheckoutIn, IdempotencyKey
from app.core.ratelimit import rate_limit
from app.orders.schemas import OrderOut

router = APIRouter(prefix="/checkout", tags=["checkout"])


@router.post(
    "",
    response_model=OrderOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("checkout", 10, 60))],
    responses={200: {"description": "Replay: this Idempotency-Key already created an order"}},
)
async def place_order(
    data: CheckoutIn,
    user: CurrentUser,
    db: DB,
    response: Response,
    idempotency_key: Annotated[IdempotencyKey, Header(alias="Idempotency-Key")],
):
    """Turns the cart into a PENDING_PAYMENT order and holds stock for the payment window.
    Send a fresh `Idempotency-Key` (e.g. a UUID) per checkout attempt and reuse it on retries."""
    order, created = await service.place_order(db, user, data, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return order
