import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

ORM = ConfigDict(from_attributes=True)


class OrderItemOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    product_id: uuid.UUID
    variant_id: uuid.UUID
    sku: str
    product_title: str
    variant_title: str
    attributes: dict
    image_url: str | None
    unit_price_paise: int
    quantity: int
    discount_paise: int
    line_total_paise: int


class StatusEventOut(BaseModel):
    model_config = ORM
    from_status: str | None
    to_status: str
    note: str | None
    created_at: datetime


class OrderSummary(BaseModel):
    model_config = ORM
    id: uuid.UUID
    number: str
    status: str
    total_paise: int
    item_count: int = 0
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    number: str
    status: str
    currency: str
    subtotal_paise: int
    discount_paise: int
    shipping_paise: int
    tax_paise: int
    total_paise: int
    prices_include_tax: bool
    coupon_code: str | None
    shipping_address: dict
    billing_address: dict
    notes: str | None
    payment_due_at: datetime | None
    paid_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    items: list[OrderItemOut]
    history: list[StatusEventOut]


Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class ReturnIn(BaseModel):
    reason: Reason


class ReturnOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    order_id: uuid.UUID
    status: str
    reason: str
    admin_note: str | None
    restocked: bool
    shipment_id: uuid.UUID | None
    created_at: datetime


class AdminCancelIn(BaseModel):
    reason: Reason
    restock: bool = True


class ApproveReturnIn(BaseModel):
    schedule_pickup: bool = True
    note: Note | None = None


class RejectReturnIn(BaseModel):
    note: Reason


class ReceiveReturnIn(BaseModel):
    restock: bool = True  # False for damaged goods
    note: Note | None = None


class TrackingEventOut(BaseModel):
    model_config = ORM
    status: str
    raw_status: str
    location: str | None
    occurred_at: datetime


class ShipmentOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    status: str
    courier: str | None
    awb: str | None
    is_return: bool
    delivered_at: datetime | None
    events: list[TrackingEventOut]


class AdminShipmentOut(ShipmentOut):
    provider: str
    provider_order_id: str
    provider_shipment_id: str
    label_url: str | None
    raw_status: str | None
    weight_grams: int


class PaymentSummary(BaseModel):
    model_config = ORM
    provider: str
    provider_order_id: str
    provider_payment_id: str | None
    status: str
    method: str | None
    amount_paise: int
    failed_attempts: int
    last_error_description: str | None
    captured_at: datetime | None


class AdminRefundOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    amount_paise: int
    status: str
    reason: str
    provider_refund_id: str | None
    failure_reason: str | None
    created_at: datetime
    processed_at: datetime | None


class AdminOrderOut(OrderOut):
    user_id: uuid.UUID
    customer_email: str
    customer_name: str
    customer_phone: str | None
    payment: PaymentSummary | None = None
    refunds: list[AdminRefundOut] = []
    shipments: list[AdminShipmentOut] = []
    returns: list[ReturnOut] = []


class AdminOrderRow(BaseModel):
    model_config = ORM
    id: uuid.UUID
    number: str
    status: str
    total_paise: int
    customer_name: str
    customer_email: str
    created_at: datetime
