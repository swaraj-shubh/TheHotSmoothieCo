import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamps, UUIDPk


class ReviewStatus(enum.StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Review(UUIDPk, Timestamps, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
        # One live review per customer per product (deleting frees the slot).
        Index(
            "uq_reviews_user_product",
            "user_id",
            "product_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # Storefront: approved reviews of a product, newest first.
        Index(
            "ix_reviews_product_public",
            "product_id",
            "created_at",
            postgresql_where=text("status = 'APPROVED' AND deleted_at IS NULL"),
        ),
        Index("ix_reviews_status_created", "status", "created_at"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rating: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(120))
    body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))
    verified_purchase: Mapped[bool] = mapped_column(server_default=text("false"))
    moderation_note: Mapped[str | None] = mapped_column(String(500))
    moderated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    media: Mapped[list["ReviewMedia"]] = relationship(lazy="selectin", order_by="ReviewMedia.sort_order")


class ReviewMedia(UUIDPk, Timestamps, Base):
    __tablename__ = "review_media"

    review_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024))
    thumbnail_url: Mapped[str] = mapped_column(String(1024))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(server_default="0")
