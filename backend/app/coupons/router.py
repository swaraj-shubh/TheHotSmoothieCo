import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth.dependencies import DB, require_roles
from app.core.pagination import MAX_LIMIT, Page
from app.core.ratelimit import rate_limit
from app.coupons import service
from app.coupons.schemas import CouponIn, CouponOut, CouponPatch
from app.users.models import RoleName, User

router = APIRouter(
    prefix="/admin/coupons", tags=["admin: coupons"], dependencies=[Depends(rate_limit("admin", 300, 60))]
)
Marketing = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.MARKETING_MANAGER))]


@router.get("", response_model=Page[CouponOut])
async def list_coupons(
    _: Marketing,
    db: DB,
    active: bool | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await service.list_coupons(db, active, cursor, limit)


@router.post("", response_model=CouponOut, status_code=status.HTTP_201_CREATED)
async def create(data: CouponIn, _: Marketing, db: DB):
    return await service.create(db, data)


@router.get("/{coupon_id}", response_model=CouponOut)
async def get(coupon_id: uuid.UUID, _: Marketing, db: DB):
    return await service.get(db, coupon_id)


@router.patch("/{coupon_id}", response_model=CouponOut)
async def update(coupon_id: uuid.UUID, data: CouponPatch, _: Marketing, db: DB):
    """Disable with `{"is_active": false}`; coupons are never deleted (orders reference them)."""
    return await service.update_coupon(db, coupon_id, data)
