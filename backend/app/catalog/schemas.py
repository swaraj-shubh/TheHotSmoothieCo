import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.catalog.models import ProductStatus

Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=200
    ),
]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
LongText = Annotated[str, StringConstraints(max_length=20_000)]
Url = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^https://", max_length=1024)]
Paise = Annotated[int, Field(ge=0, le=100_000_000)]  # ≤ ₹10,00,000 per unit
Sku = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9._-]{1,64}$")
]
Dim = Annotated[int, Field(ge=0, le=100_000)]
TagName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
SeoTitle = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
SeoDesc = Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)]

ORM = ConfigDict(from_attributes=True)


# ---------- Public ----------


class CategoryRef(BaseModel):
    model_config = ORM
    id: uuid.UUID
    name: str
    slug: str


class CategoryNode(CategoryRef):
    description: str | None
    image_url: str | None
    seo_title: str | None
    seo_description: str | None
    children: list["CategoryNode"] = []


class CollectionOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    image_url: str | None
    seo_title: str | None
    seo_description: str | None


class TagOut(BaseModel):
    model_config = ORM
    name: str
    slug: str


class MediaOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    url: str
    thumbnail_url: str
    width: int | None
    height: int | None
    alt_text: str | None
    sort_order: int
    media_type: str
    variant_id: uuid.UUID | None


class VariantOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    sku: str
    title: str
    price_paise: int
    compare_at_price_paise: int | None
    attributes: dict[str, str]
    weight_grams: int | None
    length_mm: int | None
    width_mm: int | None
    height_mm: int | None
    in_stock: bool = False
    # Capped so the storefront can limit the quantity picker without revealing exact stock.
    max_purchasable: int = 0


class OptionOut(BaseModel):
    code: str
    name: str
    values: list[str]


class ProductDetail(BaseModel):
    model_config = ORM
    id: uuid.UUID
    slug: str
    title: str
    description: str | None
    short_description: str | None
    category: CategoryRef | None
    tags: list[TagOut]
    collections: list[CategoryRef]
    seo_title: str | None
    seo_description: str | None
    min_price_paise: int | None
    max_price_paise: int | None
    rating_average: float | None = None
    rating_count: int = 0
    media: list[MediaOut]
    options: list[OptionOut] = []
    variants: list[VariantOut] = []


class ProductCard(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    short_description: str | None
    min_price_paise: int | None
    max_price_paise: int | None
    max_compare_at_price_paise: int | None
    image_url: str | None
    thumbnail_url: str | None
    image_alt: str | None
    in_stock: bool
    rating_average: float | None = None
    rating_count: int = 0


# ---------- Admin ----------


class SeoIn(BaseModel):
    seo_title: SeoTitle | None = None
    seo_description: SeoDesc | None = None


class CategoryIn(SeoIn):
    name: Title
    slug: Slug | None = None
    parent_id: uuid.UUID | None = None
    description: LongText | None = None
    image_url: Url | None = None
    sort_order: int = 0
    is_active: bool = True


class CategoryPatch(SeoIn):
    name: Title | None = None
    slug: Slug | None = None
    parent_id: uuid.UUID | None = None
    description: LongText | None = None
    image_url: Url | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class AdminCategoryOut(CategoryRef):
    parent_id: uuid.UUID | None
    description: str | None
    image_url: str | None
    sort_order: int
    is_active: bool
    seo_title: str | None
    seo_description: str | None


class CollectionIn(SeoIn):
    name: Title
    slug: Slug | None = None
    description: LongText | None = None
    image_url: Url | None = None
    sort_order: int = 0
    is_active: bool = True


class CollectionPatch(SeoIn):
    name: Title | None = None
    slug: Slug | None = None
    description: LongText | None = None
    image_url: Url | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class AdminCollectionOut(CollectionOut):
    sort_order: int
    is_active: bool


AttrCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z][a-z0-9_]{0,49}$")
]
AttrValue = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class AttributeIn(BaseModel):
    code: AttrCode
    name: Title
    sort_order: int = 0
    values: list[AttrValue] = Field(default_factory=list, max_length=200)


class AttributeValuesIn(BaseModel):
    values: list[AttrValue] = Field(min_length=1, max_length=200)


class AttributeValueOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    value: str
    slug: str
    sort_order: int


class AttributeOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    code: str
    name: str
    sort_order: int
    values: list[AttributeValueOut]


def _check_compare_at(price: int | None, compare_at: int | None) -> None:
    if price is not None and compare_at is not None and compare_at <= price:
        raise ValueError("compare_at_price_paise must be greater than price_paise")


class VariantIn(BaseModel):
    sku: Sku
    price_paise: Paise
    compare_at_price_paise: Paise | None = None
    weight_grams: Dim | None = None
    length_mm: Dim | None = None
    width_mm: Dim | None = None
    height_mm: Dim | None = None
    position: int = 0
    attributes: dict[AttrCode, AttrValue] = Field(default_factory=dict, max_length=10)
    initial_stock: int = Field(0, ge=0, le=1_000_000)
    low_stock_threshold: int = Field(5, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def _prices(self) -> "VariantIn":
        _check_compare_at(self.price_paise, self.compare_at_price_paise)
        return self


class VariantPatch(BaseModel):
    """Attributes are immutable once created — orders reference the variant; create a new one instead."""

    price_paise: Paise | None = None
    compare_at_price_paise: Paise | None = None
    weight_grams: Dim | None = None
    length_mm: Dim | None = None
    width_mm: Dim | None = None
    height_mm: Dim | None = None
    position: int | None = None
    is_active: bool | None = None


class ProductBase(SeoIn):
    description: LongText | None = None
    short_description: ShortText | None = None
    category_id: uuid.UUID | None = None
    collection_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    tags: list[TagName] = Field(default_factory=list, max_length=50)

    @field_validator("collection_ids", "tags")
    @classmethod
    def _dedupe(cls, v: list) -> list:
        return list(dict.fromkeys(v))


class ProductIn(ProductBase):
    title: Title
    slug: Slug | None = None
    status: ProductStatus = ProductStatus.DRAFT
    variants: list[VariantIn] = Field(min_length=1, max_length=100)


class ProductPatch(SeoIn):
    title: Title | None = None
    slug: Slug | None = None
    status: ProductStatus | None = None
    description: LongText | None = None
    short_description: ShortText | None = None
    category_id: uuid.UUID | None = None
    collection_ids: list[uuid.UUID] | None = Field(None, max_length=50)
    tags: list[TagName] | None = Field(None, max_length=50)


class AdminVariantOut(VariantOut):
    is_active: bool
    position: int
    on_hand: int = 0
    reserved: int = 0
    sold: int = 0
    low_stock_threshold: int = 0


class AdminProductOut(ProductDetail):
    status: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    variants: list[AdminVariantOut] = []  # type: ignore[assignment]


class AdminProductRow(BaseModel):
    model_config = ORM
    id: uuid.UUID
    title: str
    slug: str
    status: str
    min_price_paise: int | None
    max_price_paise: int | None
    created_at: datetime
    updated_at: datetime


class MediaPatch(BaseModel):
    alt_text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    sort_order: int | None = None
    variant_id: uuid.UUID | None = None
