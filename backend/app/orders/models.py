"""Orders are historical records: every name, price and address is *copied* at checkout so later
catalog or address edits never change what a customer bought or what they were charged."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamps, UUIDPk


class OrderStatus(enum.StrEnum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_PROCESSING = "PAYMENT_PROCESSING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    RETURNED = "RETURNED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


S = OrderStatus
# The only legal moves. Anything else raises InvalidStateTransition — state is never silently overwritten.
TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    S.PENDING_PAYMENT: {S.PAYMENT_PROCESSING, S.CONFIRMED, S.CANCELLED, S.FAILED},
    S.PAYMENT_PROCESSING: {S.CONFIRMED, S.FAILED, S.CANCELLED},
    S.CONFIRMED: {S.PROCESSING, S.CANCELLED, S.REFUND_PENDING},
    S.PROCESSING: {S.PACKED, S.CANCELLED, S.REFUND_PENDING},
    S.PACKED: {S.SHIPPED, S.CANCELLED, S.REFUND_PENDING},
    S.SHIPPED: {S.OUT_FOR_DELIVERY, S.DELIVERED, S.RETURNED},
    S.OUT_FOR_DELIVERY: {S.DELIVERED, S.RETURNED},
    S.DELIVERED: {S.RETURN_REQUESTED},
    S.RETURN_REQUESTED: {S.RETURNED, S.DELIVERED},  # approved / rejected
    S.RETURNED: {S.REFUND_PENDING},
    S.CANCELLED: {S.REFUND_PENDING},  # cancelled after payment -> refund
    S.REFUND_PENDING: {S.REFUNDED},
    S.REFUNDED: set(),
    S.FAILED: set(),
}
# Statuses meaning "the customer actually bought this" (first-order coupons, verified reviews).
PAID_STATUSES = {
    S.CONFIRMED,
    S.PROCESSING,
    S.PACKED,
    S.SHIPPED,
    S.OUT_FOR_DELIVERY,
    S.DELIVERED,
    S.RETURN_REQUESTED,
    S.RETURNED,
    S.REFUND_PENDING,
    S.REFUNDED,
}


class Order(UUIDPk, Timestamps, Base):
    __tablename__ = "orders"
    __table_args__ = (
        # Same Idempotency-Key from the same user can never create a second order.
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency_key"),
        Index("ix_orders_user_created", "user_id", "created_at"),
        Index("ix_orders_status_created", "status", "created_at"),
        Index("ix_orders_customer_email", "customer_email"),  # support looks orders up by email
        Index(
            "ix_orders_paid_at", "paid_at", postgresql_where=text("paid_at IS NOT NULL")
        ),  # revenue reports
        CheckConstraint(
            "subtotal_paise >= 0 AND discount_paise >= 0 AND shipping_paise >= 0 AND tax_paise >= 0 "
            "AND total_paise >= 0 AND discount_paise <= subtotal_paise",
            name="amounts_valid",
        ),
    )

    number: Mapped[str] = mapped_column(String(20), unique=True)  # customer-facing, e.g. HSC-7KQ2M9XA
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(24))
    currency: Mapped[str] = mapped_column(String(3), server_default="INR")
    subtotal_paise: Mapped[int] = mapped_column(Integer)
    discount_paise: Mapped[int] = mapped_column(Integer)
    shipping_paise: Mapped[int] = mapped_column(Integer)
    tax_paise: Mapped[int] = mapped_column(Integer)
    total_paise: Mapped[int] = mapped_column(Integer)
    prices_include_tax: Mapped[bool]
    coupon_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("coupons.id", ondelete="SET NULL"))
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    customer_email: Mapped[str] = mapped_column(String(320))
    customer_name: Mapped[str] = mapped_column(String(120))
    customer_phone: Mapped[str | None] = mapped_column(String(20))
    shipping_address: Mapped[dict] = mapped_column(JSONB)
    billing_address: Mapped[dict] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    payment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["OrderItem"]] = relationship(lazy="selectin", order_by="OrderItem.created_at")
    history: Mapped[list["OrderStatusHistory"]] = relationship(
        lazy="selectin", order_by="OrderStatusHistory.created_at"
    )


class OrderItem(UUIDPk, Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price_paise >= 0 AND discount_paise >= 0", name="amounts_valid"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="RESTRICT"), index=True)
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="RESTRICT"), index=True
    )
    # Snapshots
    sku: Mapped[str] = mapped_column(String(64))
    product_title: Mapped[str] = mapped_column(String(200))
    variant_title: Mapped[str] = mapped_column(String(200))
    attributes: Mapped[dict] = mapped_column(JSONB)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    unit_price_paise: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer)
    discount_paise: Mapped[int] = mapped_column(Integer, server_default="0")
    line_total_paise: Mapped[int] = mapped_column(Integer)  # unit * qty - discount
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrderStatusHistory(UUIDPk, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    note: Mapped[str | None] = mapped_column(String(500))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # clock_timestamp(), not now(): several transitions in one transaction must still sort correctly.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )


class ReturnStatus(enum.StrEnum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RECEIVED = "RECEIVED"


class OrderReturn(UUIDPk, Timestamps, Base):
    """Whole-order return. ponytail: per-item partial returns when the business needs them."""

    __tablename__ = "order_returns"
    __table_args__ = (
        # At most one open return per order.
        Index(
            "uq_order_returns_open", "order_id", unique=True, postgresql_where=text("status <> 'REJECTED'")
        ),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(500))
    admin_note: Mapped[str | None] = mapped_column(String(500))
    restocked: Mapped[bool] = mapped_column(server_default=text("false"))
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shipments.id", ondelete="SET NULL"))
