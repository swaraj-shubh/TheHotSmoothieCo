"""Inventory ledger.

    available = on_hand - reserved

- on_hand:  physical units in the warehouse (not yet shipped)
- reserved: units held by checkouts awaiting payment
- sold:     lifetime units sold (reporting)

The CHECK constraints are the last line of defence: even a buggy code path cannot make the
database hold more reservations than stock, or negative stock.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk


class Inventory(Timestamps, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("on_hand >= 0", name="on_hand_non_negative"),
        CheckConstraint("reserved >= 0", name="reserved_non_negative"),
        CheckConstraint("reserved <= on_hand", name="reserved_lte_on_hand"),
        CheckConstraint("low_stock_threshold >= 0", name="threshold_non_negative"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), primary_key=True
    )
    on_hand: Mapped[int] = mapped_column(Integer, server_default="0")
    reserved: Mapped[int] = mapped_column(Integer, server_default="0")
    sold: Mapped[int] = mapped_column(Integer, server_default="0")
    low_stock_threshold: Mapped[int] = mapped_column(Integer, server_default="5")

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


class TxnType(enum.StrEnum):
    INITIAL = "INITIAL"
    ADJUSTMENT = "ADJUSTMENT"  # manual correction / restock by staff
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"  # reservation cancelled or expired
    COMMIT = "COMMIT"  # payment confirmed: reserved stock leaves on_hand
    RETURN = "RETURN"  # returned goods back into stock


class InventoryTransaction(UUIDPk, Base):
    """Append-only audit trail: every change to an inventory row writes one of these."""

    __tablename__ = "inventory_transactions"
    __table_args__ = (Index("ix_inventory_transactions_variant_created", "variant_id", "created_at"),)

    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(16))
    on_hand_delta: Mapped[int] = mapped_column(Integer, server_default="0")
    reserved_delta: Mapped[int] = mapped_column(Integer, server_default="0")
    on_hand_after: Mapped[int] = mapped_column(Integer)
    reserved_after: Mapped[int] = mapped_column(Integer)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(index=True)  # order id, return id...
    reason: Mapped[str | None] = mapped_column(String(255))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReservationStatus(enum.StrEnum):
    ACTIVE = "ACTIVE"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class InventoryReservation(UUIDPk, Timestamps, Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        # One reservation per (order, variant): retrying a reserve can't double-hold stock.
        Index("uq_inventory_reservations_ref_variant", "reference_id", "variant_id", unique=True),
        # The expiry sweeper scans only live reservations.
        Index(
            "ix_inventory_reservations_active_expiry",
            "expires_at",
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    reference_id: Mapped[uuid.UUID]  # the order (FK added when the orders table exists)
    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("product_variants.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), server_default=ReservationStatus.ACTIVE)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
