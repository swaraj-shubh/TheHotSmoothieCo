import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Double, Select, and_, cast, exists, func, select, tuple_
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import (
    Attribute,
    AttributeValue,
    Collection,
    Product,
    ProductMedia,
    ProductStatus,
    ProductVariant,
    Tag,
    VariantAttributeValue,
    product_collections,
    product_tags,
)
from app.catalog.schemas import ProductCard
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.inventory.models import Inventory


class ProductSort(enum.StrEnum):
    RELEVANCE = "relevance"  # only meaningful with a text query; falls back to newest otherwise
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"


@dataclass
class ProductFilters:
    category_ids: list[uuid.UUID] | None = None
    collection_slug: str | None = None
    tag_slug: str | None = None
    min_price_paise: int | None = None
    max_price_paise: int | None = None
    in_stock: bool = False
    attributes: dict[str, list[str]] = field(default_factory=dict)  # {"size": ["a3", "a2"]}
    product_ids: list[uuid.UUID] | None = None
    text: str | None = None  # full-text query (title, description, category, tags, SKUs, options)


def text_query(q: str):
    """Prefix-matching tsquery from user input. Only word characters reach to_tsquery, so input
    can never break the query syntax. Returns None if there's nothing searchable."""
    tokens = re.findall(r"[^\W_]+", q.lower())[:8]
    return func.to_tsquery("english", " & ".join(f"{t}:*" for t in tokens)) if tokens else None


def text_rank(q: str):
    return cast(func.ts_rank_cd(Product.search_vector, text_query(q)), Double)


V = ProductVariant


def _apply_filters(stmt: Select, f: ProductFilters) -> Select:
    stmt = stmt.where(Product.status == ProductStatus.ACTIVE)
    if f.text is not None:
        # UNION of two indexed lookups (GIN on search_vector, unique btree on sku). A plain
        # `vector @@ q OR id IN (...)` defeats the GIN index and scans every product.
        tsq = text_query(f.text)
        by_sku = select(V.product_id).where(V.sku == f.text.strip().upper())
        matches = (
            by_sku.union(select(Product.id).where(Product.search_vector.op("@@")(tsq)))
            if tsq is not None
            else by_sku
        )
        stmt = stmt.where(Product.id.in_(matches))
    if f.product_ids is not None:
        stmt = stmt.where(Product.id.in_(f.product_ids))
    if f.category_ids is not None:
        stmt = stmt.where(Product.category_id.in_(f.category_ids))
    if f.collection_slug:
        stmt = stmt.where(
            exists()
            .where(product_collections.c.product_id == Product.id)
            .where(product_collections.c.collection_id == Collection.id)
            .where(Collection.slug == f.collection_slug, Collection.is_active.is_(True))
        )
    if f.tag_slug:
        stmt = stmt.where(
            exists()
            .where(product_tags.c.product_id == Product.id, product_tags.c.tag_id == Tag.id)
            .where(Tag.slug == f.tag_slug)
        )
    # Price range overlap: a product matches if any of its variants could be in range.
    if f.min_price_paise is not None:
        stmt = stmt.where(Product.max_price_paise >= f.min_price_paise)
    if f.max_price_paise is not None:
        stmt = stmt.where(Product.min_price_paise <= f.max_price_paise)

    if f.in_stock or f.attributes:
        # One variant must satisfy every condition (A3 *and* black frame *and* in stock).
        conds = [V.product_id == Product.id, V.is_active.is_(True)]
        if f.in_stock:
            conds.append(exists().where(Inventory.variant_id == V.id, Inventory.on_hand > Inventory.reserved))
        for code, value_slugs in f.attributes.items():
            conds.append(
                exists()
                .where(VariantAttributeValue.variant_id == V.id)
                .where(VariantAttributeValue.attribute_value_id == AttributeValue.id)
                .where(AttributeValue.attribute_id == Attribute.id)
                .where(Attribute.code == code, AttributeValue.slug.in_(value_slugs))
            )
        stmt = stmt.where(exists().where(and_(*conds)))
    return stmt


_SORTS = {
    # (sort column, descending?) — keyset tie-break on id in the same direction
    ProductSort.NEWEST: (Product.created_at, True),
    ProductSort.PRICE_ASC: (Product.min_price_paise, False),
    ProductSort.PRICE_DESC: (Product.min_price_paise, True),
}


async def list_product_cards(
    db: AsyncSession, f: ProductFilters, sort: ProductSort, cursor: str | None, limit: int
) -> Page[ProductCard]:
    if sort == ProductSort.RELEVANCE and f.text and text_query(f.text) is not None:
        col, desc = text_rank(f.text), True
    else:
        col, desc = _SORTS[ProductSort.NEWEST if sort == ProductSort.RELEVANCE else sort]
    stmt = _apply_filters(select(Product.id, col), f)
    if cursor:
        last_value, last_id = decode_cursor(cursor, 2)
        if col is Product.created_at:
            last_value = datetime.fromisoformat(last_value)
        key = tuple_(col, Product.id)
        stmt = stmt.where(
            key < (last_value, uuid.UUID(last_id)) if desc else key > (last_value, uuid.UUID(last_id))
        )
    order = (col.desc(), Product.id.desc()) if desc else (col.asc(), Product.id.asc())
    rows = (await db.execute(stmt.order_by(*order).limit(limit + 1))).all()

    next_cursor = encode_cursor(rows[limit - 1][1], rows[limit - 1][0]) if len(rows) > limit else None
    ids = [r[0] for r in rows[:limit]]
    return Page(items=await cards_for(db, ids), next_cursor=next_cursor)


async def cards_for(db: AsyncSession, ids: list[uuid.UUID]) -> list[ProductCard]:
    """Build cards for a page of product ids in 3 queries total, preserving order."""
    if not ids:
        return []
    products = {
        p.id: p
        for p in (
            await db.execute(
                select(
                    Product.id,
                    Product.slug,
                    Product.title,
                    Product.short_description,
                    Product.min_price_paise,
                    Product.max_price_paise,
                    Product.rating_count,
                    Product.rating_sum,
                ).where(Product.id.in_(ids))
            )
        ).all()
    }
    stats = {
        r.product_id: r
        for r in (
            await db.execute(
                select(
                    V.product_id,
                    func.max(V.compare_at_price_paise).label("max_compare"),
                    func.bool_or(Inventory.on_hand > Inventory.reserved).label("in_stock"),
                )
                .outerjoin(Inventory, Inventory.variant_id == V.id)
                .where(V.product_id.in_(ids), V.is_active.is_(True))
                .group_by(V.product_id)
            )
        ).all()
    }
    images = {
        m.product_id: m
        for m in await db.scalars(
            select(ProductMedia)
            .where(ProductMedia.product_id.in_(ids), ProductMedia.media_type == "IMAGE")
            .order_by(ProductMedia.product_id, ProductMedia.sort_order, ProductMedia.created_at)
            .ext(distinct_on(ProductMedia.product_id))
        )
    }
    cards = []
    for pid in ids:
        p, s, img = products[pid], stats.get(pid), images.get(pid)
        cards.append(
            ProductCard(
                id=p.id,
                slug=p.slug,
                title=p.title,
                short_description=p.short_description,
                min_price_paise=p.min_price_paise,
                max_price_paise=p.max_price_paise,
                max_compare_at_price_paise=s.max_compare if s else None,
                image_url=img.url if img else None,
                thumbnail_url=img.thumbnail_url if img else None,
                image_alt=(img.alt_text or p.title) if img else None,
                in_stock=bool(s and s.in_stock),
                rating_average=round(p.rating_sum / p.rating_count, 2) if p.rating_count else None,
                rating_count=p.rating_count,
            )
        )
    return cards


def product_query():
    return select(Product).execution_options(populate_existing=True)


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> Product | None:
    return await db.scalar(product_query().where(Product.id == product_id))


async def get_active_product_by_slug(db: AsyncSession, slug: str) -> Product | None:
    return await db.scalar(
        product_query().where(Product.slug == slug, Product.status == ProductStatus.ACTIVE)
    )


@dataclass(frozen=True)
class Purchasable:
    """Everything cart/checkout needs about a variant, read live from the catalog."""

    variant_id: uuid.UUID
    sku: str
    variant_title: str
    attributes: dict[str, str]
    price_paise: int
    compare_at_price_paise: int | None
    weight_grams: int | None
    product_id: uuid.UUID
    product_title: str
    product_slug: str
    category_id: uuid.UUID | None
    image_url: str | None
    available: int
    is_purchasable: bool  # variant active and product published


async def purchasables(db: AsyncSession, variant_ids: list[uuid.UUID]) -> dict[uuid.UUID, Purchasable]:
    if not variant_ids:
        return {}
    variants = list(await db.scalars(select(ProductVariant).where(ProductVariant.id.in_(variant_ids))))
    product_ids = {v.product_id for v in variants}
    products = {
        p.id: p
        for p in (
            await db.execute(
                select(Product.id, Product.title, Product.slug, Product.status, Product.category_id).where(
                    Product.id.in_(product_ids)
                )
            )
        ).all()
    }
    # Variant-specific image if there is one, else the product's first image.
    media = list(
        await db.scalars(
            select(ProductMedia)
            .where(ProductMedia.product_id.in_(product_ids), ProductMedia.media_type == "IMAGE")
            .order_by(ProductMedia.sort_order, ProductMedia.created_at)
        )
    )
    stock = dict(
        (
            await db.execute(
                select(Inventory.variant_id, Inventory.on_hand - Inventory.reserved).where(
                    Inventory.variant_id.in_(variant_ids)
                )
            )
        ).all()
    )
    out = {}
    for v in variants:
        p = products[v.product_id]
        image = next((m for m in media if m.variant_id == v.id), None) or next(
            (m for m in media if m.product_id == v.product_id), None
        )
        out[v.id] = Purchasable(
            variant_id=v.id,
            sku=v.sku,
            variant_title=v.title,
            attributes=v.attributes,
            price_paise=v.price_paise,
            compare_at_price_paise=v.compare_at_price_paise,
            weight_grams=v.weight_grams,
            product_id=p.id,
            product_title=p.title,
            product_slug=p.slug,
            category_id=p.category_id,
            image_url=image.thumbnail_url if image else None,
            available=max(stock.get(v.id, 0), 0),
            is_purchasable=v.is_active and p.status == ProductStatus.ACTIVE,
        )
    return out
