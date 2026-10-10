import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import repository as repo
from app.catalog import taxonomy
from app.catalog.models import (
    Collection,
    Product,
    ProductMedia,
    ProductStatus,
    ProductVariant,
    VariantAttributeValue,
)
from app.catalog.schemas import (
    AdminProductOut,
    AdminProductRow,
    AdminVariantOut,
    MediaPatch,
    OptionOut,
    ProductDetail,
    ProductIn,
    ProductPatch,
    VariantIn,
    VariantOut,
    VariantPatch,
)
from app.core.exceptions import AppError, Conflict, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.inventory import service as inventory
from app.inventory.models import Inventory
from app.media.storage import MediaStorage, sniff_image
from app.search.backend import get_search_backend

log = structlog.get_logger()
search = get_search_backend()

MAX_PURCHASABLE = 20  # cap on what the storefront reveals about stock
MAX_MEDIA_PER_PRODUCT = 30


class ProductNotFound(NotFound):
    code, message = "PRODUCT_NOT_FOUND", "Product not found"


class VariantNotFound(NotFound):
    code, message = "VARIANT_NOT_FOUND", "Variant not found"


class MediaNotFound(NotFound):
    code, message = "MEDIA_NOT_FOUND", "Media not found"


class SkuTaken(Conflict):
    code, message = "SKU_TAKEN", "One or more SKUs are already in use"  # duplicate within one request


class InvalidVariants(AppError):
    code, message = "INVALID_VARIANTS", "Invalid variant configuration"


# ---------- Read ----------


def _options(variants: list[ProductVariant]) -> list[OptionOut]:
    """Selector options from the variants that exist, in attribute/value sort order."""
    seen: dict[str, tuple] = {}
    for v in variants:
        for av in v.attribute_values:
            attr = av.value.attribute
            entry = seen.setdefault(attr.code, (attr.sort_order, attr.name, {}))
            entry[2][av.value.value] = av.value.sort_order
    return [
        OptionOut(code=code, name=name, values=sorted(vals, key=vals.__getitem__))
        for code, (_, name, vals) in sorted(seen.items(), key=lambda kv: (kv[1][0], kv[0]))
    ]


async def public_product(db: AsyncSession, slug: str) -> ProductDetail:
    product = await repo.get_active_product_by_slug(db, slug)
    if product is None:
        raise ProductNotFound()
    variants = [v for v in product.variants if v.is_active]
    stock = await inventory.availability(db, [v.id for v in variants])
    detail = ProductDetail.model_validate(product)
    detail.options = _options(variants)
    detail.variants = [
        VariantOut.model_validate(v).model_copy(
            update={
                "in_stock": stock.get(v.id, 0) > 0,
                "max_purchasable": min(stock.get(v.id, 0), MAX_PURCHASABLE),
            }
        )
        for v in variants
    ]
    return detail


async def admin_product(db: AsyncSession, product_id: uuid.UUID) -> AdminProductOut:
    product = await _get_product(db, product_id)
    inv = {
        i.variant_id: i
        for i in await db.scalars(
            select(Inventory).where(Inventory.variant_id.in_([v.id for v in product.variants]))
        )
    }
    out = AdminProductOut.model_validate(product)
    out.options = _options(product.variants)
    out.variants = []
    for v in product.variants:
        i = inv.get(v.id)
        out.variants.append(
            AdminVariantOut.model_validate(v).model_copy(
                update={
                    "in_stock": bool(i and i.available > 0),
                    "max_purchasable": min(i.available, MAX_PURCHASABLE) if i else 0,
                    "on_hand": i.on_hand if i else 0,
                    "reserved": i.reserved if i else 0,
                    "sold": i.sold if i else 0,
                    "low_stock_threshold": i.low_stock_threshold if i else 0,
                }
            )
        )
    return out


async def admin_list_products(
    db: AsyncSession, status: ProductStatus | None, q: str | None, cursor: str | None, limit: int
) -> Page[AdminProductRow]:
    stmt = select(Product)
    if status:
        stmt = stmt.where(Product.status == status)
    if q:
        like = f"%{q.replace('%', r'\%').replace('_', r'\_')}%"
        sku_match = select(ProductVariant.product_id).where(ProductVariant.sku.ilike(like))
        stmt = stmt.where(Product.title.ilike(like) | Product.slug.ilike(like) | Product.id.in_(sku_match))
    if cursor:
        ts, pid = decode_cursor(cursor, 2)
        stmt = stmt.where(
            tuple_(Product.created_at, Product.id) < (datetime.fromisoformat(ts), uuid.UUID(pid))
        )
    rows = list(
        await db.scalars(stmt.order_by(Product.created_at.desc(), Product.id.desc()).limit(limit + 1))
    )
    nxt = encode_cursor(rows[limit - 1].created_at, rows[limit - 1].id) if len(rows) > limit else None
    return Page(items=[AdminProductRow.model_validate(r) for r in rows[:limit]], next_cursor=nxt)


# ---------- Write helpers ----------


async def _get_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await repo.get_product(db, product_id)
    if product is None:
        raise ProductNotFound()
    return product


def _signature(attrs: dict[str, str]) -> frozenset:
    return frozenset((k, taxonomy.slugify(v)) for k, v in attrs.items())


def _validate_variant_set(variants: list[dict[str, str]]) -> None:
    """All variants of a product use the same attributes, and no two share the same combination."""
    if not variants:
        return
    codes = {frozenset(a) for a in variants}
    if len(codes) > 1:
        raise InvalidVariants("Every variant must specify the same attributes (e.g. all have size and frame)")
    sigs = [_signature(a) for a in variants]
    if len(set(sigs)) != len(sigs):
        raise InvalidVariants("Two variants have the same attribute combination")


async def _build_variant(db: AsyncSession, product: Product, data: VariantIn) -> ProductVariant:
    attrs = await taxonomy.attributes_by_code(db, set(data.attributes)) if data.attributes else {}
    links, labels = [], []
    for code, attr in sorted(attrs.items(), key=lambda kv: (kv[1].sort_order, kv[0])):
        value = (await taxonomy.resolve_attribute_values(db, attr.id, [data.attributes[code]]))[
            taxonomy.slugify(data.attributes[code])
        ]
        links.append(VariantAttributeValue(attribute_id=attr.id, attribute_value_id=value.id, value=value))
        labels.append(value.value)
    variant = ProductVariant(
        product_id=product.id,
        title=" / ".join(labels) or "Default",
        attribute_values=links,
        **data.model_dump(exclude={"attributes", "initial_stock", "low_stock_threshold"}),
    )
    db.add(variant)
    return variant


async def _refresh_price_range(db: AsyncSession, product: Product) -> None:
    lo, hi = (
        await db.execute(
            select(func.min(ProductVariant.price_paise), func.max(ProductVariant.price_paise)).where(
                ProductVariant.product_id == product.id, ProductVariant.is_active.is_(True)
            )
        )
    ).one()
    product.min_price_paise, product.max_price_paise = lo, hi


async def _set_status(db: AsyncSession, product: Product, status: ProductStatus) -> None:
    if status == ProductStatus.ACTIVE:
        active = await db.scalar(
            select(func.count()).where(
                ProductVariant.product_id == product.id, ProductVariant.is_active.is_(True)
            )
        )
        if not active:
            raise InvalidVariants("A product needs at least one active variant to be published")
        product.published_at = product.published_at or datetime.now(UTC)
    product.status = status


async def _set_relations(db: AsyncSession, product: Product, collection_ids, tags) -> None:
    if collection_ids is not None:
        cols = list(await db.scalars(select(Collection).where(Collection.id.in_(collection_ids))))
        if len(cols) != len(collection_ids):
            raise taxonomy.CollectionNotFound()
        product.collections = cols
    if tags is not None:
        product.tags = await taxonomy.get_or_create_tags(db, tags)


async def _check_category(db: AsyncSession, category_id: uuid.UUID | None) -> None:
    if category_id:
        await taxonomy._get_category(db, category_id)


# ---------- Products ----------


# Each write = a no-commit core (stage_*) reused by bulk import, plus a public wrapper that commits.


async def stage_create_product(db: AsyncSession, data: ProductIn, actor_id: uuid.UUID | None) -> Product:
    _validate_variant_set([v.attributes for v in data.variants])
    if len({v.sku for v in data.variants}) != len(data.variants):
        raise SkuTaken("Duplicate SKUs in request")
    await _check_category(db, data.category_id)

    slug = data.slug or taxonomy.slugify(data.title)
    if not data.slug and await db.scalar(select(Product.id).where(Product.slug == slug)):
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"  # auto slugs never collide; explicit ones 409

    product = Product(
        **data.model_dump(exclude={"slug", "status", "variants", "collection_ids", "tags"}),
        slug=slug,
        status=ProductStatus.DRAFT,
        variants=[],
        tags=[],
        collections=[],
        media=[],
    )
    db.add(product)
    await db.flush()
    await _set_relations(db, product, data.collection_ids, data.tags)
    for v in data.variants:
        variant = await _build_variant(db, product, v)
        await db.flush()
        await inventory.init_stock(db, variant.id, v.initial_stock, v.low_stock_threshold, actor_id)
    await _refresh_price_range(db, product)
    await _set_status(db, product, data.status)
    await search.index_product(db, product.id)  # same transaction as the change
    return product


async def create_product(db: AsyncSession, data: ProductIn, actor_id: uuid.UUID | None) -> AdminProductOut:
    product = await stage_create_product(db, data, actor_id)
    await db.commit()
    log.info("product_created", product_id=str(product.id), actor=str(actor_id))
    return await admin_product(db, product.id)


async def stage_update_product(db: AsyncSession, product_id: uuid.UUID, data: ProductPatch) -> Product:
    product = await _get_product(db, product_id)
    changes = data.model_dump(exclude_unset=True, exclude={"status", "collection_ids", "tags"})
    if "category_id" in changes:
        await _check_category(db, changes["category_id"])
    for k, v in changes.items():
        setattr(product, k, v)
    await _set_relations(db, product, data.collection_ids, data.tags)
    if data.status is not None:
        await _set_status(db, product, data.status)
    await search.index_product(db, product.id)
    return product


async def update_product(db: AsyncSession, product_id: uuid.UUID, data: ProductPatch) -> AdminProductOut:
    await stage_update_product(db, product_id, data)
    await db.commit()
    return await admin_product(db, product_id)


async def stage_add_variant(
    db: AsyncSession, product_id: uuid.UUID, data: VariantIn, actor_id: uuid.UUID | None
) -> Product:
    product = await _get_product(db, product_id)
    active = [v.attributes for v in product.variants if v.is_active]
    _validate_variant_set([*active, data.attributes])
    variant = await _build_variant(db, product, data)
    await db.flush()
    await inventory.init_stock(db, variant.id, data.initial_stock, data.low_stock_threshold, actor_id)
    await _refresh_price_range(db, product)
    await search.index_product(db, product.id)
    return product


async def add_variant(
    db: AsyncSession, product_id: uuid.UUID, data: VariantIn, actor_id: uuid.UUID | None
) -> AdminProductOut:
    await stage_add_variant(db, product_id, data, actor_id)
    await db.commit()
    return await admin_product(db, product_id)


async def stage_update_variant(
    db: AsyncSession, product_id: uuid.UUID, variant_id: uuid.UUID, data: VariantPatch
) -> Product:
    product = await _get_product(db, product_id)
    variant = next((v for v in product.variants if v.id == variant_id), None)
    if variant is None:
        raise VariantNotFound()
    changes = data.model_dump(exclude_unset=True)
    price = changes.get("price_paise", variant.price_paise)
    compare_at = changes.get("compare_at_price_paise", variant.compare_at_price_paise)
    if compare_at is not None and compare_at <= price:
        raise InvalidVariants("compare_at_price_paise must be greater than price_paise")

    if changes.get("is_active") is True and not variant.is_active:
        others = [v.attributes for v in product.variants if v.is_active and v.id != variant.id]
        _validate_variant_set([*others, variant.attributes])
    if changes.get("is_active") is False and product.status == ProductStatus.ACTIVE:
        if not any(v.is_active for v in product.variants if v.id != variant.id):
            raise InvalidVariants("Cannot deactivate the last active variant of a published product")

    for k, v in changes.items():
        setattr(variant, k, v)
    await db.flush()
    await _refresh_price_range(db, product)
    await search.index_product(db, product.id)
    return product


async def update_variant(
    db: AsyncSession, product_id: uuid.UUID, variant_id: uuid.UUID, data: VariantPatch
) -> AdminProductOut:
    await stage_update_variant(db, product_id, variant_id, data)
    await db.commit()
    return await admin_product(db, product_id)


# ---------- Media ----------


async def add_media(
    db: AsyncSession,
    storage: MediaStorage,
    folder: str,
    product_id: uuid.UUID,
    data: bytes,
    alt_text: str | None,
    variant_id: uuid.UUID | None,
) -> ProductMedia:
    product = await _get_product(db, product_id)
    if len(product.media) >= MAX_MEDIA_PER_PRODUCT:
        raise AppError(f"A product can have at most {MAX_MEDIA_PER_PRODUCT} images", code="MEDIA_LIMIT")
    if variant_id and variant_id not in {v.id for v in product.variants}:
        raise VariantNotFound()
    sniff_image(data)  # validate before spending an upload

    stored = await storage.upload(data, f"{folder}/products/{product.id}")
    media = ProductMedia(
        product_id=product.id,
        variant_id=variant_id,
        provider=stored.provider,
        storage_key=stored.key,
        url=stored.url,
        thumbnail_url=stored.thumbnail_url,
        width=stored.width,
        height=stored.height,
        format=stored.format,
        bytes=stored.bytes,
        alt_text=alt_text,
        sort_order=max((m.sort_order for m in product.media), default=-1) + 1,
    )
    db.add(media)
    try:
        await db.commit()
    except Exception:
        await storage.delete(stored.key)  # don't leave an orphaned file behind
        raise
    return media


async def _get_media(db: AsyncSession, product_id: uuid.UUID, media_id: uuid.UUID) -> ProductMedia:
    media = await db.scalar(
        select(ProductMedia).where(ProductMedia.id == media_id, ProductMedia.product_id == product_id)
    )
    if media is None:
        raise MediaNotFound()
    return media


async def update_media(db: AsyncSession, product_id: uuid.UUID, media_id: uuid.UUID, data: MediaPatch):
    media = await _get_media(db, product_id, media_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(media, k, v)
    await db.commit()
    return media


async def delete_media(db: AsyncSession, storage: MediaStorage, product_id: uuid.UUID, media_id: uuid.UUID):
    media = await _get_media(db, product_id, media_id)
    key = media.storage_key
    await db.delete(media)
    await db.commit()
    await storage.delete(key)  # after commit: a failed DB write never deletes a live image
