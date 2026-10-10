import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth.dependencies import DB, CurrentUser
from app.core.cache import cached
from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.orders import service as orders
from app.orders.schemas import ShipmentOut
from app.shipping import service
from app.shipping.provider import ShippingProvider, get_shipping_provider

router = APIRouter(
    prefix="/shipping", tags=["shipping"], dependencies=[Depends(rate_limit("shipping", 60, 60))]
)


class Serviceability(BaseModel):
    pincode: str
    serviceable: bool
    estimated_days: int | None


@router.get("/serviceability", response_model=Serviceability)
async def serviceability(
    pincode: Annotated[str, Query(pattern=r"^[1-9][0-9]{5}$")],
    provider: Annotated[ShippingProvider, Depends(get_shipping_provider)],
):
    """Can we deliver to this PIN code, and how fast? Cached per pincode for 6 hours."""

    async def load() -> dict:
        rates = await provider.rates(pincode, get_settings().default_item_weight_grams)
        days = [r.estimated_days for r in rates if r.estimated_days]
        return {"pincode": pincode, "serviceable": bool(rates), "estimated_days": min(days) if days else None}

    return await cached(f"cache:serviceability:{pincode}", 6 * 3600, load)


@router.get("/orders/{order_id}", response_model=list[ShipmentOut])
async def tracking(order_id: uuid.UUID, user: CurrentUser, db: DB):
    order = await orders.get_for_user(db, order_id, user.id)
    return await service.shipments_for_order(db, order.id)
