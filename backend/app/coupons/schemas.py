import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.coupons.models import DiscountType

CouponCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9_-]{3,40}$")
]


class CouponFields(BaseModel):
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    max_discount_paise: int | None = Field(None, gt=0, le=100_000_000)
    min_subtotal_paise: int = Field(0, ge=0, le=100_000_000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    usage_limit: int | None = Field(None, gt=0)
    per_user_limit: int | None = Field(1, gt=0)
    first_order_only: bool = False
    is_active: bool = True
    product_ids: list[uuid.UUID] = Field(default_factory=list, max_length=500)
    category_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


class CouponIn(CouponFields):
    code: CouponCode
    discount_type: DiscountType
    value: int = Field(gt=0, le=100_000_000, description="percent (1-100) or paise")

    @model_validator(mode="after")
    def _check(self) -> "CouponIn":
        if self.discount_type == DiscountType.PERCENT and self.value > 100:
            raise ValueError("Percentage discount must be between 1 and 100")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class CouponPatch(BaseModel):
    """Code, type and value are immutable once created (orders reference them): make a new coupon."""

    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)] | None = None
    max_discount_paise: int | None = Field(None, gt=0, le=100_000_000)
    min_subtotal_paise: int | None = Field(None, ge=0, le=100_000_000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    usage_limit: int | None = Field(None, gt=0)
    per_user_limit: int | None = Field(None, gt=0)
    first_order_only: bool | None = None
    is_active: bool | None = None
    product_ids: list[uuid.UUID] | None = Field(None, max_length=500)
    category_ids: list[uuid.UUID] | None = Field(None, max_length=100)


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    description: str | None
    discount_type: str
    value: int
    max_discount_paise: int | None
    min_subtotal_paise: int
    starts_at: datetime | None
    ends_at: datetime | None
    usage_limit: int | None
    per_user_limit: int | None
    first_order_only: bool
    is_active: bool
    times_used: int
    product_ids: list[uuid.UUID] = []
    category_ids: list[uuid.UUID] = []
    created_at: datetime
