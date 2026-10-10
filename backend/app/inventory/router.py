import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.auth.dependencies import DB, require_roles
from app.core.pagination import MAX_LIMIT, Page
from app.core.ratelimit import rate_limit
from app.inventory import service
from app.inventory.schemas import AdjustIn, StockRow, TransactionOut
from app.users.models import RoleName, User

router = APIRouter(
    prefix="/admin/inventory",
    tags=["admin: inventory"],
    dependencies=[Depends(rate_limit("admin", 300, 60))],
)
InventoryStaff = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.INVENTORY_MANAGER))]


@router.get("", response_model=Page[StockRow])
async def stock(
    _: InventoryStaff,
    db: DB,
    low_stock: bool = False,
    q: Annotated[str | None, Query(max_length=64, description="SKU prefix")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await service.stock_list(db, low_stock_only=low_stock, q=q, cursor=cursor, limit=limit)


@router.post("/{variant_id}/adjust", status_code=status.HTTP_204_NO_CONTENT)
async def adjust(variant_id: uuid.UUID, data: AdjustIn, user: InventoryStaff, db: DB):
    await service.admin_adjust(db, variant_id, data, user.id)


@router.get("/{variant_id}/history", response_model=Page[TransactionOut])
async def history(
    variant_id: uuid.UUID,
    _: InventoryStaff,
    db: DB,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await service.history(db, variant_id, cursor, limit)
