import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Plain text only (the frontend escapes on render); control characters are rejected.
ReviewTitle = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=120, pattern=r"^[^\x00-\x08\x0b-\x1f\x7f]*$"
    ),
]
ReviewBody = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=5000, pattern=r"^[^\x00-\x08\x0b-\x1f\x7f]*$")
]
ORM = ConfigDict(from_attributes=True)


class ReviewIn(BaseModel):
    product_id: uuid.UUID
    rating: int = Field(ge=1, le=5)
    title: ReviewTitle | None = None
    body: ReviewBody | None = None


class ReviewPatch(BaseModel):
    rating: int | None = Field(None, ge=1, le=5)
    title: ReviewTitle | None = None
    body: ReviewBody | None = None


class ReviewMediaOut(BaseModel):
    model_config = ORM
    id: uuid.UUID
    url: str
    thumbnail_url: str
    width: int | None
    height: int | None


class PublicReview(BaseModel):
    id: uuid.UUID
    rating: int
    title: str | None
    body: str | None
    author: str  # "Ada L." — never the full name or email
    verified_purchase: bool
    media: list[ReviewMediaOut]
    created_at: datetime


class MyReview(BaseModel):
    model_config = ORM
    id: uuid.UUID
    product_id: uuid.UUID
    rating: int
    title: str | None
    body: str | None
    status: str
    verified_purchase: bool
    moderation_note: str | None
    media: list[ReviewMediaOut]
    created_at: datetime
    updated_at: datetime


class AdminReview(MyReview):
    user_id: uuid.UUID
    moderated_at: datetime | None
    # Filled by the queue listing so moderators see context, not UUIDs.
    product_title: str | None = None
    product_slug: str | None = None
    author_email: str | None = None


class ReviewSummary(BaseModel):
    count: int
    average: float | None
    distribution: dict[int, int]  # {5: 12, 4: 3, ...}


class ModerateIn(BaseModel):
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
