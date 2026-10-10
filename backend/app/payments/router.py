import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import DB, CurrentUser
from app.core.exceptions import NotFound
from app.core.ratelimit import rate_limit
from app.payments import service
from app.payments.provider import DevPaymentProvider, PaymentProvider, get_payment_provider
from app.payments.schemas import InitiateOut, PaymentStatusOut, VerifyIn

router = APIRouter(
    prefix="/payments", tags=["payments"], dependencies=[Depends(rate_limit("payments", 30, 60))]
)
Provider = Annotated[PaymentProvider, Depends(get_payment_provider)]


@router.post("/orders/{order_id}/initiate", response_model=InitiateOut)
async def initiate(order_id: uuid.UUID, user: CurrentUser, db: DB, provider: Provider):
    """Creates (or reuses) the gateway order; pass the result to the Razorpay Checkout widget."""
    return await service.initiate(db, provider, user, order_id)


@router.post("/orders/{order_id}/verify", response_model=PaymentStatusOut)
async def verify(order_id: uuid.UUID, data: VerifyIn, user: CurrentUser, db: DB, provider: Provider):
    """Widget success callback. Signature-checked and re-fetched from the gateway; the webhook
    confirms the same payment independently if this call never arrives."""
    return await service.verify_client(db, provider, user, order_id, data)


@router.get("/orders/{order_id}", response_model=PaymentStatusOut)
async def payment_status(order_id: uuid.UUID, user: CurrentUser, db: DB):
    """Poll after checkout while waiting for the webhook."""
    return await service.status(db, user, order_id)


class SimulateIn(BaseModel):
    outcome: Literal["success", "failure"] = "success"


@router.post("/orders/{order_id}/simulate", response_model=PaymentStatusOut)
async def simulate(order_id: uuid.UUID, data: SimulateIn, user: CurrentUser, db: DB, provider: Provider):
    """Development only (PAYMENTS_PROVIDER=dev): complete or decline the payment for an order."""
    if not isinstance(provider, DevPaymentProvider):
        raise NotFound()
    return await service.simulate_dev_payment(db, provider, user, order_id, data.outcome == "success")
