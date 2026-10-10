from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import DB
from app.catalog.repository import ProductFilters, ProductSort
from app.catalog.router import build_filters
from app.core.pagination import MAX_LIMIT
from app.core.ratelimit import rate_limit
from app.search.backend import SearchBackend, SearchPage, Suggestion, get_search_backend

router = APIRouter(prefix="/search", tags=["search"], dependencies=[Depends(rate_limit("search", 120, 60))])
Backend = Annotated[SearchBackend, Depends(get_search_backend)]
Q = Annotated[str, Query(min_length=1, max_length=100)]


@router.get("", response_model=SearchPage)
async def search(
    q: Q,
    db: DB,
    backend: Backend,
    filters: Annotated[ProductFilters, Depends(build_filters)],
    sort: ProductSort = ProductSort.RELEVANCE,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 24,
):
    """Keyword search with every catalog filter (category, price, size/frame, stock) and sorting."""
    return await backend.search(db, q, filters, sort, cursor, limit)


@router.get("/suggest", response_model=list[Suggestion])
async def suggest(q: Q, db: DB, backend: Backend, limit: Annotated[int, Query(ge=1, le=10)] = 8):
    """Search-as-you-type."""
    return await backend.suggest(db, q, limit)
