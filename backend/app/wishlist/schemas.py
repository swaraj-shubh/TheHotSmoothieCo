import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.catalog.schemas import ProductCard


class WishlistIn(BaseModel):
    product_id: uuid.UUID
    variant_id: uuid.UUID | None = None


class MoveToCartIn(BaseModel):
    variant_id: uuid.UUID | None = None  # required if the saved item has no variant and there are several
    quantity: int = Field(1, ge=1, le=100)


class WishlistVariant(BaseModel):
    id: uuid.UUID
    title: str
    price_paise: int
    in_stock: bool


class WishlistItemOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    product: ProductCard
    variant: WishlistVariant | None
