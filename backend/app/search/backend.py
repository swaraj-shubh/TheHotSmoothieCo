"""Search behind a small interface. Postgres full-text + trigram today; an OpenSearch/Algolia
backend would implement the same three methods and the API/frontend wouldn't change."""

import uuid
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import repository as catalog
from app.catalog.models import Product, ProductStatus
from app.catalog.repository import ProductFilters, ProductSort
from app.catalog.schemas import ProductCard


class SearchPage(BaseModel):
    items: list[ProductCard]
    next_cursor: str | None = None
    fuzzy: bool = False  # true when no exact match and we're showing near-misses ("Did you mean")


class Suggestion(BaseModel):
    slug: str
    title: str


class SearchBackend(Protocol):
    async def search(
        self,
        db: AsyncSession,
        q: str,
        filters: ProductFilters,
        sort: ProductSort,
        cursor: str | None,
        limit: int,
    ) -> SearchPage: ...
    async def suggest(self, db: AsyncSession, q: str, limit: int) -> list[Suggestion]: ...
    async def index_product(self, db: AsyncSession, product_id: uuid.UUID) -> None: ...


def build_document(product: Product) -> str:
    """Everything searchable that isn't a plain product column."""
    parts = [product.description or ""]
    if product.category:
        parts.append(product.category.name)
    parts += [c.name for c in product.collections]
    parts += [t.name for t in product.tags]
    for v in product.variants:
        if v.is_active:
            parts.append(v.sku)
            parts += list(v.attributes.values())
    return " ".join(p for p in parts if p)[:100_000]


class PostgresSearch:
    FUZZY_MIN_SIMILARITY = 0.3

    async def search(
        self,
        db: AsyncSession,
        q: str,
        filters: ProductFilters,
        sort: ProductSort,
        cursor: str | None,
        limit: int,
    ) -> SearchPage:
        filters.text = q
        page = await catalog.list_product_cards(db, filters, sort, cursor, limit)
        if page.items or cursor:
            return SearchPage(items=page.items, next_cursor=page.next_cursor)
        # Nothing matched: typo-tolerant title similarity (pg_trgm), first page only.
        filters.text = None
        stmt = catalog._apply_filters(select(Product.id), filters).where(Product.title.op("%")(q))
        ids = list(await db.scalars(stmt.order_by(func.similarity(Product.title, q).desc()).limit(limit)))
        return SearchPage(items=await catalog.cards_for(db, ids), fuzzy=bool(ids))

    async def suggest(self, db: AsyncSession, q: str, limit: int) -> list[Suggestion]:
        tsq = catalog.text_query(q)
        if tsq is None:
            return []
        rows = await db.execute(
            select(Product.slug, Product.title)
            .where(Product.status == ProductStatus.ACTIVE, Product.search_vector.op("@@")(tsq))
            .order_by(func.ts_rank_cd(Product.search_vector, tsq).desc(), Product.title)
            .limit(limit)
        )
        return [Suggestion(slug=slug, title=title) for slug, title in rows]

    async def index_product(self, db: AsyncSession, product_id: uuid.UUID) -> None:
        product = await catalog.get_product(db, product_id)
        if product is not None:
            await db.execute(
                update(Product)
                .where(Product.id == product_id)
                .values(search_document=build_document(product))
            )


async def reindex_all(db: AsyncSession, batch: int = 200) -> int:
    """Catches anything per-product indexing can't see (e.g. a category rename). Only rewrites
    rows whose document actually changed, so the GIN index isn't churned needlessly."""
    changed, last_id = 0, None
    while True:
        stmt = select(Product.id).order_by(Product.id).limit(batch)
        if last_id:
            stmt = stmt.where(Product.id > last_id)
        ids = list(await db.scalars(stmt))
        if not ids:
            break
        for pid in ids:
            product = await catalog.get_product(db, pid)
            if product and product.search_document != (doc := build_document(product)):
                product.search_document = doc
                changed += 1
        await db.commit()
        db.expunge_all()  # keep memory flat over a large catalog
        last_id = ids[-1]
    return changed


def get_search_backend() -> SearchBackend:
    return PostgresSearch()
