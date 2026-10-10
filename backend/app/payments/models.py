import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk


class PaymentStatus(enum.StrEnum):
    CREATED = "CREATED"  # gateway order exists; customer may attempt (and retry) payment
    AUTHORIZED = "AUTHORIZED"  # bank approved, capture pending
    CAPTURED = "CAPTURED"  # money received


class Payment(UUIDPk, Timestamps, Base):
    """One gateway order per shop order. Failed attempts don't create rows: the customer retries
    against the same gateway order, and the last failure is kept for support."""

    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payments_order_id"),
        UniqueConstraint("provider", "provider_order_id", name="uq_payments_provider_order"),
        CheckConstraint("amount_paise > 0", name="amount_positive"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(20))
    provider_order_id: Mapped[str] = mapped_column(String(64))
    provider_payment_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16))
    method: Mapped[str | None] = mapped_column(String(30))
    failed_attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_description: Mapped[str | None] = mapped_column(String(500))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefundStatus(enum.StrEnum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class Refund(UUIDPk, Timestamps, Base):
    __tablename__ = "refunds"
    __table_args__ = (
        # The same refund request (retry, double click, duplicate job) can never refund twice.
        UniqueConstraint("idempotency_key", name="uq_refunds_idempotency_key"),
        CheckConstraint("amount_paise > 0", name="amount_positive"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), index=True)
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id", ondelete="RESTRICT"))
    # Usually the order's captured payment; differs when refunding a duplicate capture.
    provider_payment_id: Mapped[str] = mapped_column(String(64), index=True)
    provider_refund_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(255))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    failure_reason: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookStatus(enum.StrEnum):
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    IGNORED = "IGNORED"
    FAILED = "FAILED"


class WebhookEvent(UUIDPk, Base):
    """Every verified inbound webhook. The unique (provider, event_id) makes redelivery a no-op,
    and FAILED rows are the dead-letter list for investigation."""

    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),)

    provider: Mapped[str] = mapped_column(String(20))
    event_id: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), index=True)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    error: Mapped[str | None] = mapped_column(String(1000))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
