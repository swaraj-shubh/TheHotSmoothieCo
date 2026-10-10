import enum
import uuid

from pydantic import BaseModel, Field

from app.coupons.schemas import CouponCode


class LineIssue(enum.StrEnum):
    UNAVAILABLE = "UNAVAILABLE"  # variant/product no longer sold
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"  # fewer in stock than in cart


class AddItemIn(BaseModel):
    variant_id: uuid.UUID
    quantity: int = Field(1, ge=1, le=100)


class UpdateItemIn(BaseModel):
    quantity: int = Field(ge=1, le=100)


class ApplyCouponIn(BaseModel):
    code: CouponCode


class TotalsOut(BaseModel):
    subtotal_paise: int
    discount_paise: int
    shipping_paise: int
    tax_paise: int
    total_paise: int
    prices_include_tax: bool


class CartItemOut(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    product_id: uuid.UUID
    product_slug: str
    product_title: str
    variant_title: str
    sku: str
    attributes: dict[str, str]
    image_url: str | None
    unit_price_paise: int
    compare_at_price_paise: int | None
    quantity: int
    line_total_paise: int
    max_purchasable: int
    issue: LineIssue | None = None


class CartOut(BaseModel):
    id: uuid.UUID | None
    items: list[CartItemOut]
    item_count: int
    coupon_code: str | None
    coupon_error: str | None = None
    totals: TotalsOut
    checkout_ready: bool
    # Returned only when a guest cart is created: the client stores it (cookie) and sends it back
    # as the X-Cart-Token header.
    cart_token: str | None = None
