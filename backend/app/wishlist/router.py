import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth.dependencies import DB, CurrentUser
from app.cart import service as cart_service
from app.cart.schemas import CartOut
from app.core.pagination import MAX_LIMIT, Page
from app.core.ratelimit import rate_limit
from app.wishlist import service
from app.wishlist.schemas import MoveToCartIn, WishlistIn, WishlistItemOut

router = APIRouter(
    prefix="/wishlist", tags=["wishlist"], dependencies=[Depends(rate_limit("wishlist", 120, 60))]
)


@router.get("", response_model=Page[WishlistItemOut])
async def list_items(
    user: CurrentUser,
    db: DB,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 24,
):
    return await service.list_items(db, user.id, cursor, limit)


@router.post("", response_model=WishlistItemOut, status_code=status.HTTP_201_CREATED)
async def add(data: WishlistIn, user: CurrentUser, db: DB):
    return await service.add(db, user.id, data)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(item_id: uuid.UUID, user: CurrentUser, db: DB):
    await service.remove(db, user.id, item_id)


@router.post("/{item_id}/move-to-cart", response_model=CartOut)
async def move_to_cart(item_id: uuid.UUID, data: MoveToCartIn, user: CurrentUser, db: DB):
    cart = await service.move_to_cart(db, user.id, item_id, data)
    return await cart_service.view(db, cart, user.id)
