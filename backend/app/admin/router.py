"""Admin dashboard, analytics, customers, staff roles, audit log, banners and catalog CSV.
(Catalog, inventory, orders, coupons, reviews and notifications admin live in their modules.)"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, tuple_

from app.admin import analytics, service
from app.admin.analytics import Interval, SalesPoint, TopProduct
from app.admin.models import BannerPlacement
from app.admin.service import (
    AuditOut,
    BannerIn,
    BannerOut,
    CustomerDetail,
    CustomerRow,
    CustomerStatusIn,
    RolesIn,
    StaffOut,
)
from app.auth.dependencies import DB, require_roles
from app.catalog import csv_io
from app.catalog.models import Product, ProductMedia
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.pagination import MAX_LIMIT, Page, decode_cursor, encode_cursor
from app.core.ratelimit import rate_limit
from app.users.models import RoleName, User

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(rate_limit("admin", 300, 60))])
public_router = APIRouter(tags=["storefront"])

Admin = Annotated[User, Depends(require_roles(RoleName.ADMIN))]
SuperAdmin = Annotated[User, Depends(require_roles())]  # SUPER_ADMIN only
Analyst = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.MARKETING_MANAGER))]
Support = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.CUSTOMER_SUPPORT))]
Marketing = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.MARKETING_MANAGER))]
Catalog = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.PRODUCT_MANAGER))]
# Any staff role can see the overview; what each can *do* is enforced per endpoint.
Staff = Annotated[User, Depends(require_roles(*RoleName))]


def _default_range(start: date | None, end: date | None) -> tuple[date, date]:
    end = end or datetime.now(analytics.IST).date()
    return start or end - timedelta(days=29), end


@router.get("/dashboard")
async def dashboard(_: Staff, db: DB):
    return await analytics.dashboard(db)


@router.get("/analytics/sales", response_model=list[SalesPoint], tags=["admin: analytics"])
async def sales(
    _: Analyst,
    db: DB,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    interval: Interval = Interval.DAY,
):
    start, end = _default_range(from_, to)
    return await analytics.sales(db, start, end, interval)


@router.get("/analytics/top-products", response_model=list[TopProduct], tags=["admin: analytics"])
async def top_products(
    _: Analyst,
    db: DB,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
    by: Literal["revenue", "units"] = "revenue",
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
):
    start, end = _default_range(from_, to)
    return await analytics.top_products(db, start, end, by, limit)


@router.get("/analytics/customers", tags=["admin: analytics"])
async def customer_analytics(
    _: Analyst, db: DB, from_: Annotated[date | None, Query(alias="from")] = None, to: date | None = None
):
    start, end = _default_range(from_, to)
    return await analytics.customer_stats(db, start, end)


# ---------- Customers ----------


@router.get("/customers", response_model=Page[CustomerRow], tags=["admin: customers"])
async def customers(
    _: Support,
    db: DB,
    q: Annotated[str | None, Query(max_length=100, description="email, name or phone")] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await service.list_customers(db, q, cursor, limit)


@router.get("/customers/{user_id}", response_model=CustomerDetail, tags=["admin: customers"])
async def customer(user_id: uuid.UUID, _: Support, db: DB):
    return await service.customer_detail(db, user_id)


@router.patch("/customers/{user_id}", response_model=CustomerDetail, tags=["admin: customers"])
async def customer_status(user_id: uuid.UUID, data: CustomerStatusIn, _: Admin, db: DB):
    """Deactivating signs the customer out of every device immediately."""
    return await service.set_customer_status(db, user_id, data)


# ---------- Staff ----------


@router.get("/users", response_model=list[StaffOut], tags=["admin: staff"])
async def staff(_: SuperAdmin, db: DB):
    return await service.list_staff(db)


@router.put("/users/{user_id}/roles", response_model=StaffOut, tags=["admin: staff"])
async def set_roles(user_id: uuid.UUID, data: RolesIn, actor: SuperAdmin, db: DB):
    return await service.set_roles(db, actor, user_id, data.roles)


# ---------- Audit ----------


@router.get("/audit-logs", response_model=Page[AuditOut], tags=["admin: audit"])
async def audit_logs(
    _: Admin,
    db: DB,
    actor_id: uuid.UUID | None = None,
    target_id: Annotated[str | None, Query(max_length=64)] = None,
    target_type: Annotated[str | None, Query(max_length=60)] = None,
    since: datetime | None = None,
    until: datetime | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await service.list_audit(
        db,
        actor_id=actor_id,
        target_id=target_id,
        target_type=target_type,
        since=since,
        until=until,
        cursor=cursor,
        limit=limit,
    )


# ---------- Banners ----------


@router.get("/banners", response_model=list[BannerOut], tags=["admin: marketing"])
async def list_banners(_: Marketing, db: DB):
    return await service.list_banners(db)


@router.post(
    "/banners", response_model=BannerOut, status_code=status.HTTP_201_CREATED, tags=["admin: marketing"]
)
async def create_banner(data: BannerIn, _: Marketing, db: DB):
    return await service.save_banner(db, data)


@router.put("/banners/{banner_id}", response_model=BannerOut, tags=["admin: marketing"])
async def update_banner(banner_id: uuid.UUID, data: BannerIn, _: Marketing, db: DB):
    return await service.save_banner(db, data, banner_id)


@router.delete("/banners/{banner_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["admin: marketing"])
async def delete_banner(banner_id: uuid.UUID, _: Marketing, db: DB):
    await service.delete_banner(db, banner_id)


@public_router.get("/banners", response_model=list[BannerOut])
async def storefront_banners(db: DB, placement: BannerPlacement = BannerPlacement.HOME_HERO):
    return await service.public_banners(db, placement)


# ---------- Catalog CSV ----------


@router.get("/products/export.csv", tags=["admin: catalog"])
async def export_products(_: Catalog):
    async def stream():
        # Own session: the request-scoped one closes before a streaming body finishes.
        async with SessionLocal() as db:
            async for chunk in csv_io.export_rows(db):
                yield chunk

    filename = f"products-{datetime.now(UTC):%Y%m%d-%H%M}.csv"
    return StreamingResponse(
        stream(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/products/import", tags=["admin: catalog"])
async def import_products(
    user: Catalog,
    db: DB,
    file: Annotated[UploadFile, File()],
    dry_run: bool = True,  # safe default: validate first, then re-run with dry_run=false
):
    """All-or-nothing. Errors come back per row (422-style details) and nothing is saved."""
    data = await file.read(csv_io.MAX_BYTES + 1)
    return await csv_io.import_csv(db, data, user.id, dry_run)


# ---------- Media library & settings ----------


class MediaItem(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_title: str
    product_slug: str
    url: str
    thumbnail_url: str
    alt_text: str | None
    width: int | None
    height: int | None
    bytes: int | None
    created_at: datetime


@router.get("/media", response_model=Page[MediaItem], tags=["admin: catalog"])
async def media_library(
    _: Catalog,
    db: DB,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 48,
):
    """Every product image, newest first (uploads happen on the product page)."""
    stmt = select(ProductMedia, Product.title, Product.slug).join(
        Product, Product.id == ProductMedia.product_id
    )
    if cursor:
        ts, mid = decode_cursor(cursor, 2)
        stmt = stmt.where(
            tuple_(ProductMedia.created_at, ProductMedia.id) < (datetime.fromisoformat(ts), uuid.UUID(mid))
        )
    rows = (
        await db.execute(
            stmt.order_by(ProductMedia.created_at.desc(), ProductMedia.id.desc()).limit(limit + 1)
        )
    ).all()
    items = [
        MediaItem(
            id=m.id,
            product_id=m.product_id,
            product_title=title,
            product_slug=slug,
            url=m.url,
            thumbnail_url=m.thumbnail_url,
            alt_text=m.alt_text,
            width=m.width,
            height=m.height,
            bytes=m.bytes,
            created_at=m.created_at,
        )
        for m, title, slug in rows[:limit]
    ]
    return Page(
        items=items,
        next_cursor=encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None,
    )


@router.get("/settings", tags=["admin"])
async def store_settings(_: Staff):
    """Read-only view of store policy and which integrations are configured (never secrets)."""
    s = get_settings()
    return {
        "environment": s.environment,
        "pricing": {
            "prices_include_tax": s.prices_include_tax,
            "tax_rate_bps": s.tax_rate_bps,
            "shipping_flat_paise": s.shipping_flat_paise,
            "free_shipping_threshold_paise": s.free_shipping_threshold_paise,
            "return_window_days": s.return_window_days,
            "inventory_hold_seconds": s.inventory_hold_seconds,
        },
        "integrations": {
            "payments": s.payments_provider
            if s.payments_provider == "dev"
            else ("razorpay" if s.razorpay_key_id and s.razorpay_key_secret else None),
            "shipping": "shiprocket" if s.shiprocket_email and s.shiprocket_password else None,
            "media": "cloudinary" if s.cloudinary_cloud_name and s.cloudinary_api_key else None,
            "email": "smtp"
            if s.smtp_host
            else ("console" if s.environment in ("development", "test") else None),
            "error_tracking": "sentry" if s.sentry_dsn else None,
        },
    }
