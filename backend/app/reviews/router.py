import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.auth.dependencies import DB, CurrentUser, require_roles
from app.core.config import get_settings
from app.core.pagination import MAX_LIMIT, Page
from app.core.ratelimit import rate_limit
from app.media.storage import MAX_IMAGE_BYTES, InvalidUpload, MediaStorage, get_media_storage
from app.reviews import service
from app.reviews.models import ReviewStatus
from app.reviews.schemas import (
    AdminReview,
    ModerateIn,
    MyReview,
    PublicReview,
    ReviewIn,
    ReviewPatch,
    ReviewSummary,
)
from app.users.models import RoleName, User

router = APIRouter(tags=["reviews"])
Moderator = Annotated[
    User, Depends(require_roles(RoleName.ADMIN, RoleName.PRODUCT_MANAGER, RoleName.CUSTOMER_SUPPORT))
]
write_limit = [Depends(rate_limit("review_write", 20, 3600))]


@router.get("/products/{slug}/reviews", response_model=Page[PublicReview])
async def product_reviews(
    slug: str,
    db: DB,
    rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
):
    return await service.public_reviews(db, slug, rating, cursor, limit)


@router.get("/products/{slug}/reviews/summary", response_model=ReviewSummary)
async def review_summary(slug: str, db: DB):
    return await service.summary(db, slug)


@router.get("/reviews/mine", response_model=list[MyReview])
async def my_reviews(user: CurrentUser, db: DB):
    return await service.my_reviews(db, user.id)


@router.post(
    "/reviews", response_model=MyReview, status_code=status.HTTP_201_CREATED, dependencies=write_limit
)
async def create(data: ReviewIn, user: CurrentUser, db: DB):
    """Every review is moderated before it appears; verified-purchase badge is computed server-side."""
    return await service.create(db, user, data)


@router.patch("/reviews/{review_id}", response_model=MyReview, dependencies=write_limit)
async def update(review_id: uuid.UUID, data: ReviewPatch, user: CurrentUser, db: DB):
    return await service.update_review(db, user, review_id, data)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(review_id: uuid.UUID, user: CurrentUser, db: DB):
    await service.delete_review(db, user, review_id)


@router.post("/reviews/{review_id}/media", response_model=MyReview, dependencies=write_limit)
async def upload_photo(
    review_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    file: Annotated[UploadFile, File()],
):
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidUpload()
    return await service.add_media(db, storage, get_settings().media_folder, user, review_id, data)


@router.get("/admin/reviews", response_model=Page[AdminReview], tags=["admin: reviews"])
async def moderation_queue(
    _: Moderator,
    db: DB,
    status_: Annotated[ReviewStatus | None, Query(alias="status")] = ReviewStatus.PENDING,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await service.admin_list(db, status_, cursor, limit)


@router.post("/admin/reviews/{review_id}/approve", response_model=AdminReview, tags=["admin: reviews"])
async def approve(review_id: uuid.UUID, data: ModerateIn, user: Moderator, db: DB):
    return await service.moderate(db, review_id, ReviewStatus.APPROVED, data.note, user.id)


@router.post("/admin/reviews/{review_id}/reject", response_model=AdminReview, tags=["admin: reviews"])
async def reject(review_id: uuid.UUID, data: ModerateIn, user: Moderator, db: DB):
    return await service.moderate(db, review_id, ReviewStatus.REJECTED, data.note, user.id)
