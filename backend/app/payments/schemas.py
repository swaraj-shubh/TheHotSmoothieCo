import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ProviderId = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_]{1,64}$")]


class Prefill(BaseModel):
    name: str
    email: str
    contact: str | None


class InitiateOut(BaseModel):
    """Everything the frontend passes to the gateway's checkout widget."""

    provider: str
    public_key: str
    provider_order_id: str
    amount_paise: int
    currency: str
    order_id: uuid.UUID
    order_number: str
    payment_due_at: datetime | None
    prefill: Prefill


class VerifyIn(BaseModel):
    provider_order_id: ProviderId
    provider_payment_id: ProviderId
    signature: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class PaymentStatusOut(BaseModel):
    order_id: uuid.UUID
    order_status: str
    payment_status: str | None


class RefundIn(BaseModel):
    amount_paise: int | None = Field(None, gt=0, description="omit for the full remaining amount")
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]


class RefundOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    amount_paise: int
    status: str
    reason: str
    failure_reason: str | None
    created_at: datetime
    processed_at: datetime | None
