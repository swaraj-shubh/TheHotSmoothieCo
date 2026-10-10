import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class StockRow(BaseModel):
    variant_id: uuid.UUID
    sku: str
    product_id: uuid.UUID
    product_title: str
    variant_title: str
    on_hand: int
    reserved: int
    available: int
    sold: int
    low_stock_threshold: int
    low_stock: bool


class AdjustIn(BaseModel):
    """Exactly one of `delta` (+10 restock, -2 damaged) or `set_to` (absolute, after a stock count)."""

    delta: int | None = Field(None, ge=-1_000_000, le=1_000_000)
    set_to: int | None = Field(None, ge=0, le=1_000_000)
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=255)]
    low_stock_threshold: int | None = Field(None, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def _one_of(self) -> "AdjustIn":
        if (self.delta is None) == (self.set_to is None):
            raise ValueError("Provide exactly one of delta or set_to")
        if self.delta == 0:
            raise ValueError("delta must be non-zero")
        return self


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    on_hand_delta: int
    reserved_delta: int
    on_hand_after: int
    reserved_after: int
    reference_id: uuid.UUID | None
    reason: str | None
    actor_user_id: uuid.UUID | None
    created_at: datetime
