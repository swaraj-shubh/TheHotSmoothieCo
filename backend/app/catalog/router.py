"""Public storefront catalog API (no auth)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import DB
from app.catalog import repository as repo
from app.catalog import service, taxonomy
from app.catalog.repository import ProductFilters, ProductSort
from app.catalog.schemas import AttributeOut, CategoryNode, CollectionOut, ProductCard, ProductDetail
from app.core.exceptions import AppError
from app.core.pagination import MAX_LIMIT, Page
from app.core.ratelimit import rate_limit

router = APIRouter(tags=["catalog"], dependencies=[Depends(rate_limit("public_catalog", 600, 60))])


@router.get("/categories", response_model=list[CategoryNode])
async def categories(db: DB):
    return await taxonomy.category_tree(db)


@router.get("/categories/{slug}", response_model=CategoryNode)
async def category(slug: str, db: DB):
    return await taxonomy.category_by_slug(db, slug)


@router.get("/attributes", response_model=list[AttributeOut])
async def attributes(db: DB):
    """Filterable options (Size, Frame, Paper…) for storefront filters. Cached for an hour."""
    return await taxonomy.public_attributes(db)


@router.get("/collections", response_model=list[CollectionOut])
async def collections(db: DB):
    return await taxonomy.list_collections(db)


@router.get("/collections/{slug}", response_model=CollectionOut)
async def collection(slug: str, db: DB):
    return await taxonomy.collection_by_slug(db, slug)


def parse_attr_filters(attr: list[str]) -> dict[str, list[str]]:
    """`?attr=size:a3&attr=size:a2&attr=frame:black` -> {"size": ["a3", "a2"], "frame": ["black"]}"""
    out: dict[str, list[str]] = {}
    for item in attr[:20]:
        code, sep, value = item.partition(":")
        if not sep or not code or not value:
            raise AppError("attr filters look like attr=size:a3", code="INVALID_FILTER")
        out.setdefault(code.lower(), []).append(value.lower())
    return out


async def build_filters(
    db: DB,
    category: str | None = None,
    collection: str | None = None,
    tag: str | None = None,
    min_price: Annotated[int | None, Query(ge=0, description="paise")] = None,
    max_price: Annotated[int | None, Query(ge=0, description="paise")] = None,
    in_stock: bool = False,
    attr: Annotated[list[str], Query()] = [],  # noqa: B006 (FastAPI copies defaults)
) -> ProductFilters:
    return ProductFilters(
        category_ids=await taxonomy.category_ids_with_descendants(db, category) if category else None,
        collection_slug=collection,
        tag_slug=tag,
        min_price_paise=min_price,
        max_price_paise=max_price,
        in_stock=in_stock,
        attributes=parse_attr_filters(attr),
    )


@router.get("/products", response_model=Page[ProductCard])
async def products(
    db: DB,
    filters: Annotated[ProductFilters, Depends(build_filters)],
    sort: ProductSort = ProductSort.NEWEST,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 24,
):
    return await repo.list_product_cards(db, filters, sort, cursor, limit)


@router.get("/products/{slug}", response_model=ProductDetail)
async def product(slug: str, db: DB):
    return await service.public_product(db, slug)
