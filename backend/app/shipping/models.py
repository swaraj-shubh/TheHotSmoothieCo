import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamps, UUIDPk


class Shipment(UUIDPk, Timestamps, Base):
    """Our local copy of shipment state; the frontend never talks to the courier directly."""

    __tablename__ = "shipments"
    __table_args__ = (
        # One live forward shipment per order (a cancelled one can be replaced).
        Index(
            "uq_shipments_active_forward",
            "order_id",
            unique=True,
            postgresql_where=text("is_return = false AND status <> 'CANCELLED'"),
        ),
        Index("ix_shipments_status", "status"),
    )

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_order_id: Mapped[str] = mapped_column(String(64))
    provider_shipment_id: Mapped[str] = mapped_column(String(64))
    awb: Mapped[str | None] = mapped_column(String(64), unique=True)
    courier: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20))
    raw_status: Mapped[str | None] = mapped_column(String(120))
    label_url: Mapped[str | None] = mapped_column(String(1024))
    is_return: Mapped[bool] = mapped_column(server_default=text("false"))
    weight_grams: Mapped[int] = mapped_column(Integer)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    events: Mapped[list["ShipmentTrackingEvent"]] = relationship(
        lazy="selectin", order_by="ShipmentTrackingEvent.occurred_at"
    )


class ShipmentTrackingEvent(UUIDPk, Base):
    __tablename__ = "shipment_tracking_events"
    __table_args__ = (
        # Webhook + polling report the same scans; store each once.
        UniqueConstraint("shipment_id", "occurred_at", "raw_status", name="uq_tracking_event"),
    )

    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20))
    raw_status: Mapped[str] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
