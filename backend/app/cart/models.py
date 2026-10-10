import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamps, UUIDPk


class Cart(UUIDPk, Timestamps, Base):
    """Either a user's cart (one per user) or a guest cart found by a secret token (only its hash is
    stored). Carts never store prices: they are always read live from the catalog."""

    __tablename__ = "carts"
    __table_args__ = (
        Index("uq_carts_user", "user_id", unique=True, postgresql_where=text("user_id IS NOT NULL")),
        CheckConstraint("user_id IS NOT NULL OR guest_token_hash IS NOT NULL", name="has_owner"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    guest_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    coupon_code: Mapped[str | None] = mapped_column(String(40))
    abandoned_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["CartItem"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="CartItem.created_at"
    )


class CartItem(UUIDPk, Timestamps, Base):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("cart_id", "variant_id"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

    cart_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"))
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
