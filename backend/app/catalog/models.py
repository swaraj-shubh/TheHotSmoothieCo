"""Catalog schema.

Money is stored as integer paise everywhere (no floats, maps 1:1 to Razorpay amounts).

Variants use *global* attributes (Size, Frame, Paper...) rather than per-product free text, so the
storefront can filter "all A3 posters" across the catalog. Each variant has exactly one value per
attribute it uses: PK(variant_id, attribute_id) on variant_attribute_values.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamps, UUIDPk


class ProductStatus(enum.StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class MediaType(enum.StrEnum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class SeoMixin:
    seo_title: Mapped[str | None] = mapped_column(String(160))
    seo_description: Mapped[str | None] = mapped_column(String(320))


class Category(UUIDPk, Timestamps, SeoMixin, Base):
    __tablename__ = "categories"

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    sort_order: Mapped[int] = mapped_column(server_default="0")
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class Collection(UUIDPk, Timestamps, SeoMixin, Base):
    __tablename__ = "collections"

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    sort_order: Mapped[int] = mapped_column(server_default="0")
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class Tag(UUIDPk, Base):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(60))
    slug: Mapped[str] = mapped_column(String(80), unique=True)


product_tags = Table(
    "product_tags",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True),
)

product_collections = Table(
    "product_collections",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("collection_id", ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Attribute(UUIDPk, Base):
    __tablename__ = "attributes"

    code: Mapped[str] = mapped_column(String(50), unique=True)  # "size", "frame", "paper"
    name: Mapped[str] = mapped_column(String(80))  # "Size"
    sort_order: Mapped[int] = mapped_column(server_default="0")

    values: Mapped[list["AttributeValue"]] = relationship(
        back_populates="attribute", order_by="AttributeValue.sort_order", lazy="selectin"
    )


class AttributeValue(UUIDPk, Base):
    __tablename__ = "attribute_values"
    __table_args__ = (UniqueConstraint("attribute_id", "slug"),)

    attribute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attributes.id", ondelete="CASCADE"))
    value: Mapped[str] = mapped_column(String(80))  # "A3", "Black Frame"
    slug: Mapped[str] = mapped_column(String(100))  # "a3", "black-frame" (used in filters)
    sort_order: Mapped[int] = mapped_column(server_default="0")

    attribute: Mapped[Attribute] = relationship(back_populates="values", lazy="joined")


class Product(UUIDPk, Timestamps, SeoMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("status IN ('DRAFT', 'ACTIVE', 'ARCHIVED')", name="status"),
        # Storefront listing: active products by recency / price.
        Index("ix_products_active_created", "created_at", "id", postgresql_where=text("status = 'ACTIVE'")),
        Index(
            "ix_products_active_price", "min_price_paise", "id", postgresql_where=text("status = 'ACTIVE'")
        ),
        Index("ix_products_search_vector", "search_vector", postgresql_using="gin"),
        # Typo-tolerant fallback; needs the pg_trgm extension (created in the migration).
        Index(
            "ix_products_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
    )

    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    short_description: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), server_default=ProductStatus.DRAFT, index=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    # Denormalised from active variants (kept in sync by the catalog service) for cheap
    # listing, price filtering and price sorting without aggregating variants per request.
    min_price_paise: Mapped[int | None] = mapped_column(Integer)
    max_price_paise: Mapped[int | None] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Approved-review aggregate, recomputed (never incremented) by the reviews service.
    rating_count: Mapped[int] = mapped_column(Integer, server_default="0")
    rating_sum: Mapped[int] = mapped_column(Integer, server_default="0")
    # Search: search_document is maintained by app.search (category, tags, SKUs, options...);
    # the weighted tsvector is computed by Postgres so it can never be out of sync with it.
    search_document: Mapped[str | None] = mapped_column(Text)
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('english', coalesce(short_description, '')), 'B') || "
            "setweight(to_tsvector('english', coalesce(search_document, '')), 'C')",
            persisted=True,
        ),
    )

    @property
    def rating_average(self) -> float | None:
        return round(self.rating_sum / self.rating_count, 2) if self.rating_count else None

    category: Mapped[Category | None] = relationship(lazy="joined")
    tags: Mapped[list[Tag]] = relationship(secondary=product_tags, lazy="selectin", order_by=Tag.name)
    collections: Mapped[list[Collection]] = relationship(secondary=product_collections, lazy="selectin")
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", order_by="ProductVariant.position", lazy="selectin"
    )
    media: Mapped[list["ProductMedia"]] = relationship(order_by="ProductMedia.sort_order", lazy="selectin")


class VariantAttributeValue(Base):
    __tablename__ = "variant_attribute_values"

    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), primary_key=True
    )
    attribute_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attributes.id", ondelete="RESTRICT"), primary_key=True
    )
    attribute_value_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_values.id", ondelete="RESTRICT"), index=True
    )

    value: Mapped[AttributeValue] = relationship(lazy="joined")


class ProductVariant(UUIDPk, Timestamps, Base):
    """The purchasable unit. Never hard-deleted once sold: deactivate instead."""

    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("price_paise >= 0", name="price_non_negative"),
        CheckConstraint(
            "compare_at_price_paise IS NULL OR compare_at_price_paise > price_paise",
            name="compare_at_gt_price",
        ),
        CheckConstraint("weight_grams IS NULL OR weight_grams >= 0", name="weight_non_negative"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(200))  # "A3 / Black Frame", derived from attribute values
    price_paise: Mapped[int] = mapped_column(Integer)
    compare_at_price_paise: Mapped[int | None] = mapped_column(Integer)
    weight_grams: Mapped[int | None] = mapped_column(Integer)
    length_mm: Mapped[int | None] = mapped_column(Integer)
    width_mm: Mapped[int | None] = mapped_column(Integer)
    height_mm: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(server_default="0")
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))

    product: Mapped[Product] = relationship(back_populates="variants")
    attribute_values: Mapped[list[VariantAttributeValue]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def attributes(self) -> dict[str, str]:
        # Stable order (attribute sort_order, then code): API responses and CSV exports never shuffle.
        ordered = sorted(
            self.attribute_values, key=lambda av: (av.value.attribute.sort_order, av.value.attribute.code)
        )
        return {av.value.attribute.code: av.value.value for av in ordered}


class ProductMedia(UUIDPk, Timestamps, Base):
    """Metadata only; the binary lives in the media storage provider (Cloudinary/S3/R2)."""

    __tablename__ = "product_media"
    __table_args__ = (CheckConstraint("media_type IN ('IMAGE', 'VIDEO')", name="media_type"),)

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(32))
    storage_key: Mapped[str] = mapped_column(String(512))  # Cloudinary public_id / S3 object key
    url: Mapped[str] = mapped_column(String(1024))
    thumbnail_url: Mapped[str] = mapped_column(String(1024))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    format: Mapped[str | None] = mapped_column(String(16))
    bytes: Mapped[int | None] = mapped_column(Integer)
    alt_text: Mapped[str | None] = mapped_column(String(300))
    sort_order: Mapped[int] = mapped_column(server_default="0")
    media_type: Mapped[str] = mapped_column(String(10), server_default=MediaType.IMAGE)
