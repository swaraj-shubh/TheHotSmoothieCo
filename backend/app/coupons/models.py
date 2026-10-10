import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamps, UUIDPk


class DiscountType(enum.StrEnum):
    PERCENT = "PERCENT"
    FIXED = "FIXED"


coupon_products = Table(
    "coupon_products",
    Base.metadata,
    Column("coupon_id", ForeignKey("coupons.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
)

coupon_categories = Table(
    "coupon_categories",
    Base.metadata,
    Column("coupon_id", ForeignKey("coupons.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Coupon(UUIDPk, Timestamps, Base):
    __tablename__ = "coupons"
    __table_args__ = (
        CheckConstraint("discount_type IN ('PERCENT', 'FIXED')", name="discount_type"),
        CheckConstraint(
            "(discount_type = 'PERCENT' AND value BETWEEN 1 AND 100) "
            "OR (discount_type = 'FIXED' AND value > 0)",
            name="value_range",
        ),
        CheckConstraint("usage_limit IS NULL OR times_used <= usage_limit", name="usage_within_limit"),
        CheckConstraint("times_used >= 0", name="times_used_non_negative"),
    )

    code: Mapped[str] = mapped_column(String(40), unique=True)  # stored upper-case
    description: Mapped[str | None] = mapped_column(String(255))
    discount_type: Mapped[str] = mapped_column(String(10))
    value: Mapped[int] = mapped_column(Integer)
    max_discount_paise: Mapped[int | None] = mapped_column(Integer)
    min_subtotal_paise: Mapped[int] = mapped_column(Integer, server_default="0")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usage_limit: Mapped[int | None] = mapped_column(Integer)  # total redemptions across everyone
    per_user_limit: Mapped[int | None] = mapped_column(Integer, server_default="1")
    first_order_only: Mapped[bool] = mapped_column(server_default=text("false"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    times_used: Mapped[int] = mapped_column(Integer, server_default="0")

    products = relationship("Product", secondary=coupon_products, lazy="selectin")
    categories = relationship("Category", secondary=coupon_categories, lazy="selectin")


class CouponUsage(UUIDPk, Base):
    """One row per order that used a coupon. Deleted (and times_used decremented) if that order
    is cancelled before payment, so abandoned checkouts don't burn a customer's single use."""

    __tablename__ = "coupon_usages"

    coupon_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("coupons.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    discount_paise: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
