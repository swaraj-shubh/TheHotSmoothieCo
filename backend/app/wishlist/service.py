import uuid
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.cart import service as cart_service
from app.catalog import repository as catalog
from app.catalog.models import Product, ProductStatus, ProductVariant
from app.core.exceptions import AppError, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.wishlist.models import WishlistItem
from app.wishlist.schemas import MoveToCartIn, WishlistIn, WishlistItemOut, WishlistVariant


class WishlistItemNotFound(NotFound):
    code, message = "WISHLIST_ITEM_NOT_FOUND", "Item not in wishlist"


class ProductUnavailable(NotFound):
    code, message = "PRODUCT_NOT_FOUND", "Product not found"


async def add(db: AsyncSession, user_id: uuid.UUID, data: WishlistIn) -> WishlistItemOut:
    product = await db.scalar(
        select(Product.id).where(Product.id == data.product_id, Product.status == ProductStatus.ACTIVE)
    )
    if product is None:
        raise ProductUnavailable()
    if data.variant_id and not await db.scalar(
        select(ProductVariant.id).where(
            ProductVariant.id == data.variant_id, ProductVariant.product_id == data.product_id
        )
    ):
        raise AppError("Variant does not belong to this product", code="VARIANT_MISMATCH")
    # Idempotent: saving twice returns the existing entry.
    await db.execute(
        insert(WishlistItem)
        .values(id=uuid.uuid4(), user_id=user_id, product_id=data.product_id, variant_id=data.variant_id)
        .on_conflict_do_nothing()
    )
    await db.commit()
    item = await db.scalar(
        select(WishlistItem).where(
            WishlistItem.user_id == user_id,
            WishlistItem.product_id == data.product_id,
            WishlistItem.variant_id.is_not_distinct_from(data.variant_id),
        )
    )
    assert item is not None
    return (await _render(db, [item]))[0]


async def _render(db: AsyncSession, items: list[WishlistItem]) -> list[WishlistItemOut]:
    cards = {c.id: c for c in await catalog.cards_for(db, list({i.product_id for i in items}))}
    variants = await catalog.purchasables(db, [i.variant_id for i in items if i.variant_id])
    out = []
    for i in items:
        if i.product_id not in cards:
            continue
        v = variants.get(i.variant_id) if i.variant_id else None
        out.append(
            WishlistItemOut(
                id=i.id,
                created_at=i.created_at,
                product=cards[i.product_id],
                variant=WishlistVariant(
                    id=v.variant_id,
                    title=v.variant_title,
                    price_paise=v.price_paise,
                    in_stock=v.is_purchasable and v.available > 0,
                )
                if v
                else None,
            )
        )
    return out


async def list_items(
    db: AsyncSession, user_id: uuid.UUID, cursor: str | None, limit: int
) -> Page[WishlistItemOut]:
    stmt = select(WishlistItem).where(WishlistItem.user_id == user_id)
    if cursor:
        ts, wid = decode_cursor(cursor, 2)
        stmt = stmt.where(
            tuple_(WishlistItem.created_at, WishlistItem.id) < (datetime.fromisoformat(ts), uuid.UUID(wid))
        )
    rows = list(
        await db.scalars(
            stmt.order_by(WishlistItem.created_at.desc(), WishlistItem.id.desc()).limit(limit + 1)
        )
    )
    page = rows[:limit]
    nxt = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
    # ponytail: archived products are skipped in the page (it can come back shorter than `limit`).
    return Page(items=await _render(db, page), next_cursor=nxt)


async def _get(db: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID) -> WishlistItem:
    item = await db.scalar(
        select(WishlistItem).where(WishlistItem.id == item_id, WishlistItem.user_id == user_id)
    )
    if item is None:
        raise WishlistItemNotFound()
    return item


async def remove(db: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID) -> None:
    await db.delete(await _get(db, user_id, item_id))
    await db.commit()


async def move_to_cart(db: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID, data: MoveToCartIn):
    item = await _get(db, user_id, item_id)
    variant_id = data.variant_id or item.variant_id
    if variant_id is None:
        active = list(
            await db.scalars(
                select(ProductVariant.id).where(
                    ProductVariant.product_id == item.product_id, ProductVariant.is_active.is_(True)
                )
            )
        )
        if len(active) != 1:
            raise AppError("Choose a size/option first", code="VARIANT_REQUIRED")
        variant_id = active[0]
    elif not await db.scalar(
        select(ProductVariant.id).where(
            ProductVariant.id == variant_id, ProductVariant.product_id == item.product_id
        )
    ):
        raise AppError("Variant does not belong to this product", code="VARIANT_MISMATCH")

    cart, _ = await cart_service.get_cart(db, user_id, None, create=True)
    assert cart is not None
    await db.delete(item)
    # add_item commits: wishlist removal and cart add land together, or (out of stock) neither does.
    return await cart_service.add_item(db, cart, variant_id, data.quantity)
