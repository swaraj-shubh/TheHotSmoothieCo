import asyncio
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin.router import public_router as storefront_router
from app.admin.router import router as admin_router
from app.audit.middleware import AuditMiddleware
from app.auth.router import router as auth_router
from app.cart.router import router as cart_router
from app.catalog.admin_router import router as catalog_admin_router
from app.catalog.router import router as catalog_router
from app.checkout.router import router as checkout_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.exceptions import register_exception_handlers
from app.core.limits import BodySizeLimitMiddleware
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.redis import redis
from app.coupons.router import router as coupons_admin_router
from app.health.router import router as health_router
from app.inventory.router import router as inventory_admin_router
from app.notifications.router import router as notifications_router
from app.orders.admin_router import router as orders_admin_router
from app.orders.router import router as orders_router
from app.payments.router import router as payments_router
from app.reviews.router import router as reviews_router
from app.search.router import router as search_router
from app.shipping.router import router as shipping_router
from app.users.router import router as users_router
from app.webhooks.router import router as webhooks_router
from app.wishlist.router import router as wishlist_router

settings = get_settings()
configure_logging(settings.debug)

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        traces_sample_rate=0.1,
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    stop, scheduler = asyncio.Event(), None
    if settings.run_worker_in_api:
        # Single-service deployments (e.g. a free-tier host without background workers).
        # Safe with several API instances: each job is guarded by a Postgres advisory lock.
        from app.workers.runner import run_loop

        scheduler = asyncio.create_task(run_loop(stop))
    yield
    if scheduler:
        stop.set()
        await scheduler
    await redis.aclose()
    await engine.dispose()


app = FastAPI(
    title=f"{settings.app_name} API",
    version="1.0.0",
    lifespan=lifespan,
    # API docs are public in dev/staging only; production schema isn't advertised.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Order: last added = outermost. RequestContext > Audit > CORS > BodySizeLimit > app.
app.add_middleware(
    BodySizeLimitMiddleware
)  # innermost wrapper: rejects before any body parsing, CORS headers still apply
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(AuditMiddleware)  # inside RequestContext so audit rows carry the request ID
app.add_middleware(RequestContextMiddleware)  # outermost: every response gets a request ID
register_exception_handlers(app)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth_router)
api_v1.include_router(users_router)
api_v1.include_router(catalog_router)
# Before catalog admin: /admin/products/export.csv must win over /admin/products/{product_id}.
api_v1.include_router(admin_router)
api_v1.include_router(storefront_router)
api_v1.include_router(catalog_admin_router)
api_v1.include_router(inventory_admin_router)
api_v1.include_router(cart_router)
api_v1.include_router(wishlist_router)
api_v1.include_router(checkout_router)
api_v1.include_router(orders_router)
api_v1.include_router(coupons_admin_router)
api_v1.include_router(payments_router)
api_v1.include_router(shipping_router)
api_v1.include_router(orders_admin_router)
api_v1.include_router(webhooks_router)
api_v1.include_router(reviews_router)
api_v1.include_router(search_router)
api_v1.include_router(notifications_router)

app.include_router(health_router)
app.include_router(api_v1)
