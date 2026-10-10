import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPk


class WishlistItem(UUIDPk, Base):
    """One wishlist per user, so items hang off the user directly (no separate wishlists table)."""

    __tablename__ = "wishlist_items"
    __table_args__ = (
        # NULLS NOT DISTINCT: "product without a chosen variant" can only be saved once too.
        Index(
            "uq_wishlist_items_user_product_variant",
            "user_id",
            "product_id",
            "variant_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_wishlist_items_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
