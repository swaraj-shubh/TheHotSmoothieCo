import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Product, ProductStatus
from app.core.exceptions import AppError, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.media.storage import MediaStorage, sniff_image
from app.orders.models import PAID_STATUSES, Order, OrderItem
from app.reviews.models import Review, ReviewMedia, ReviewStatus
from app.reviews.schemas import (
    AdminReview,
    PublicReview,
    ReviewIn,
    ReviewMediaOut,
    ReviewPatch,
    ReviewSummary,
)
from app.users.models import User

log = structlog.get_logger()
MAX_MEDIA = 4


class ReviewNotFound(NotFound):
    code, message = "REVIEW_NOT_FOUND", "Review not found"


def _now() -> datetime:
    return datetime.now(UTC)


def display_name(full_name: str) -> str:
    parts = full_name.split()
    return f"{parts[0]} {parts[-1][0]}." if len(parts) > 1 else (parts[0] if parts else "Customer")


async def _verified(db: AsyncSession, user_id: uuid.UUID, product_id: uuid.UUID) -> bool:
    return bool(
        await db.scalar(
            select(OrderItem.id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(
                Order.user_id == user_id, OrderItem.product_id == product_id, Order.status.in_(PAID_STATUSES)
            )
            .limit(1)
        )
    )


async def refresh_rating(db: AsyncSession, product_id: uuid.UUID) -> None:
    """Recompute from approved reviews: idempotent, can't drift like += / -= counters."""
    count, total = (
        await db.execute(
            select(func.count(), func.coalesce(func.sum(Review.rating), 0)).where(
                Review.product_id == product_id,
                Review.status == ReviewStatus.APPROVED,
                Review.deleted_at.is_(None),
            )
        )
    ).one()
    await db.execute(
        update(Product).where(Product.id == product_id).values(rating_count=count, rating_sum=total)
    )


async def _own(db: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID) -> Review:
    review = await db.scalar(
        select(Review)
        .where(Review.id == review_id, Review.user_id == user_id, Review.deleted_at.is_(None))
        .execution_options(populate_existing=True)
    )
    if review is None:
        raise ReviewNotFound()
    return review


async def create(db: AsyncSession, user: User, data: ReviewIn) -> Review:
    if not await db.scalar(
        select(Product.id).where(Product.id == data.product_id, Product.status == ProductStatus.ACTIVE)
    ):
        raise NotFound("Product not found", code="PRODUCT_NOT_FOUND")
    review = Review(
        product_id=data.product_id,
        user_id=user.id,
        rating=data.rating,
        title=data.title,
        body=data.body,
        status=ReviewStatus.PENDING,
        verified_purchase=await _verified(db, user.id, data.product_id),
        media=[],
    )
    db.add(review)
    await db.commit()  # a second live review hits uq_reviews_user_product -> REVIEW_EXISTS
    return review


async def update_review(db: AsyncSession, user: User, review_id: uuid.UUID, data: ReviewPatch) -> Review:
    review = await _own(db, user.id, review_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        if k == "rating" and v is None:
            continue
        setattr(review, k, v)
    review.status = ReviewStatus.PENDING  # edited text must be re-moderated
    review.verified_purchase = await _verified(db, user.id, review.product_id)
    await refresh_rating(db, review.product_id)
    await db.commit()
    return await _own(db, user.id, review_id)


async def delete_review(db: AsyncSession, user: User, review_id: uuid.UUID) -> None:
    review = await _own(db, user.id, review_id)
    review.deleted_at = _now()
    await refresh_rating(db, review.product_id)
    await db.commit()


async def add_media(
    db: AsyncSession, storage: MediaStorage, folder: str, user: User, review_id: uuid.UUID, data: bytes
) -> Review:
    review = await _own(db, user.id, review_id)
    if len(review.media) >= MAX_MEDIA:
        raise AppError(f"A review can have at most {MAX_MEDIA} photos", code="MEDIA_LIMIT")
    sniff_image(data)
    stored = await storage.upload(data, f"{folder}/reviews/{review.id}")
    db.add(
        ReviewMedia(
            review_id=review.id,
            provider=stored.provider,
            storage_key=stored.key,
            url=stored.url,
            thumbnail_url=stored.thumbnail_url,
            width=stored.width,
            height=stored.height,
            sort_order=len(review.media),
        )
    )
    review.status = ReviewStatus.PENDING  # photos are moderated too
    await refresh_rating(db, review.product_id)
    try:
        await db.commit()
    except Exception:
        await storage.delete(stored.key)
        raise
    return await _own(db, user.id, review_id)


async def my_reviews(db: AsyncSession, user_id: uuid.UUID) -> list[Review]:
    return list(
        await db.scalars(
            select(Review)
            .where(Review.user_id == user_id, Review.deleted_at.is_(None))
            .order_by(Review.created_at.desc())
            .limit(200)
        )
    )


# ---------- Storefront ----------


async def _product_id(db: AsyncSession, slug: str) -> uuid.UUID:
    pid = await db.scalar(
        select(Product.id).where(Product.slug == slug, Product.status == ProductStatus.ACTIVE)
    )
    if pid is None:
        raise NotFound("Product not found", code="PRODUCT_NOT_FOUND")
    return pid


async def public_reviews(
    db: AsyncSession, slug: str, rating: int | None, cursor: str | None, limit: int
) -> Page[PublicReview]:
    pid = await _product_id(db, slug)
    stmt = (
        select(Review, User.full_name)
        .join(User, User.id == Review.user_id)
        .where(Review.product_id == pid, Review.status == ReviewStatus.APPROVED, Review.deleted_at.is_(None))
    )
    if rating:
        stmt = stmt.where(Review.rating == rating)
    if cursor:
        ts, rid = decode_cursor(cursor, 2)
        stmt = stmt.where(tuple_(Review.created_at, Review.id) < (datetime.fromisoformat(ts), uuid.UUID(rid)))
    rows = (
        await db.execute(stmt.order_by(Review.created_at.desc(), Review.id.desc()).limit(limit + 1))
    ).all()
    items = [
        PublicReview(
            id=r.id,
            rating=r.rating,
            title=r.title,
            body=r.body,
            author=display_name(name),
            verified_purchase=r.verified_purchase,
            media=[ReviewMediaOut.model_validate(m) for m in r.media],
            created_at=r.created_at,
        )
        for r, name in rows[:limit]
    ]
    nxt = encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None
    return Page(items=items, next_cursor=nxt)


async def summary(db: AsyncSession, slug: str) -> ReviewSummary:
    pid = await _product_id(db, slug)
    rows = (
        await db.execute(
            select(Review.rating, func.count())
            .where(
                Review.product_id == pid, Review.status == ReviewStatus.APPROVED, Review.deleted_at.is_(None)
            )
            .group_by(Review.rating)
        )
    ).all()
    dist = {star: 0 for star in range(5, 0, -1)} | dict(rows)
    count = sum(dist.values())
    avg = round(sum(k * v for k, v in dist.items()) / count, 2) if count else None
    return ReviewSummary(count=count, average=avg, distribution=dist)


# ---------- Moderation ----------


async def admin_list(
    db: AsyncSession, status: ReviewStatus | None, cursor: str | None, limit: int
) -> Page[AdminReview]:
    stmt = (
        select(Review, Product.title, Product.slug, User.email)
        .join(Product, Product.id == Review.product_id)
        .join(User, User.id == Review.user_id)
        .where(Review.deleted_at.is_(None))
    )
    if status:
        stmt = stmt.where(Review.status == status)
    if cursor:
        ts, rid = decode_cursor(cursor, 2)
        stmt = stmt.where(tuple_(Review.created_at, Review.id) > (datetime.fromisoformat(ts), uuid.UUID(rid)))
    # Oldest first: the moderation queue is worked FIFO.
    rows = (await db.execute(stmt.order_by(Review.created_at, Review.id).limit(limit + 1))).all()
    items = [
        AdminReview.model_validate(r).model_copy(
            update={"product_title": t, "product_slug": sl, "author_email": e}
        )
        for r, t, sl, e in rows[:limit]
    ]
    nxt = encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None
    return Page(items=items, next_cursor=nxt)


async def moderate(
    db: AsyncSession, review_id: uuid.UUID, to: ReviewStatus, note: str | None, actor_id: uuid.UUID
) -> Review:
    review = await db.scalar(
        select(Review)
        .where(Review.id == review_id, Review.deleted_at.is_(None))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if review is None:
        raise ReviewNotFound()
    review.status, review.moderation_note = to, note
    review.moderated_by, review.moderated_at = actor_id, _now()
    await refresh_rating(db, review.product_id)
    await db.commit()
    log.info("review_moderated", review_id=str(review.id), status=to, actor=str(actor_id))
    return review
