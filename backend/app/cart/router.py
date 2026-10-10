import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.auth.dependencies import DB, CurrentUser, OptionalUser
from app.cart import service
from app.cart.models import Cart
from app.cart.schemas import AddItemIn, ApplyCouponIn, CartOut, UpdateItemIn
from app.core.ratelimit import rate_limit
from app.coupons.service import InvalidCoupon

router = APIRouter(prefix="/cart", tags=["cart"], dependencies=[Depends(rate_limit("cart", 120, 60))])
CartToken = Annotated[str | None, Header(alias="X-Cart-Token", max_length=256)]


async def _existing(db, user, token) -> Cart:
    cart, _ = await service.get_cart(db, user.id if user else None, token)
    if cart is None:
        raise service.CartNotFound()
    return cart


@router.get("", response_model=CartOut)
async def get_cart(db: DB, user: OptionalUser, token: CartToken = None):
    cart, _ = await service.get_cart(db, user.id if user else None, token)
    return await service.view(db, cart, user.id if user else None)


@router.post("/items", response_model=CartOut)
async def add_item(data: AddItemIn, db: DB, user: OptionalUser, token: CartToken = None):
    cart, new_token = await service.get_cart(db, user.id if user else None, token, create=True)
    assert cart is not None
    cart = await service.add_item(db, cart, data.variant_id, data.quantity)
    return await service.view(db, cart, user.id if user else None, new_token)


@router.patch("/items/{item_id}", response_model=CartOut)
async def update_item(
    item_id: uuid.UUID, data: UpdateItemIn, db: DB, user: OptionalUser, token: CartToken = None
):
    cart = await service.update_item(db, await _existing(db, user, token), item_id, data.quantity)
    return await service.view(db, cart, user.id if user else None)


@router.delete("/items/{item_id}", response_model=CartOut)
async def remove_item(item_id: uuid.UUID, db: DB, user: OptionalUser, token: CartToken = None):
    cart = await service.remove_item(db, await _existing(db, user, token), item_id)
    return await service.view(db, cart, user.id if user else None)


@router.delete("", response_model=CartOut)
async def clear_cart(db: DB, user: OptionalUser, token: CartToken = None):
    cart = await service.clear(db, await _existing(db, user, token))
    return await service.view(db, cart, user.id if user else None)


@router.post("/coupon", response_model=CartOut, dependencies=[Depends(rate_limit("coupon", 20, 300))])
async def apply_coupon(data: ApplyCouponIn, db: DB, user: OptionalUser, token: CartToken = None):
    cart, _ = await service.get_cart(db, user.id if user else None, token)
    if cart is None:
        raise InvalidCoupon("Add something to your cart first")
    cart = await service.apply_coupon(db, cart, user.id if user else None, data.code)
    return await service.view(db, cart, user.id if user else None)


@router.delete("/coupon", response_model=CartOut)
async def remove_coupon(db: DB, user: OptionalUser, token: CartToken = None):
    cart = await service.remove_coupon(db, await _existing(db, user, token))
    return await service.view(db, cart, user.id if user else None)


@router.post("/merge", response_model=CartOut)
async def merge(db: DB, user: CurrentUser, token: CartToken = None):
    """Call right after login with the guest X-Cart-Token; the guest cart is folded in and deleted."""
    cart = await service.merge_guest_cart(db, user.id, token)
    return await service.view(db, cart, user.id)
