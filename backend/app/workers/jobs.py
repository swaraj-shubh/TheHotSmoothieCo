"""Periodic jobs. Each is idempotent and safe to run concurrently with the API; the runner ensures
only one instance of a given job runs at a time across all worker processes."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_

from app.auth.models import UserSession, UserToken
from app.cart import service as cart
from app.core.database import SessionLocal
from app.notifications import service as notifications
from app.orders import service as orders
from app.payments import service as payments
from app.payments.models import WebhookEvent, WebhookStatus
from app.payments.provider import optional_payment_provider
from app.search.backend import reindex_all
from app.shipping import service as shipping
from app.shipping.provider import optional_shipping_provider


async def drain_notifications() -> int:
    return await notifications.drain()


async def expire_unpaid_orders() -> int:
    async with SessionLocal() as db:
        return await orders.expire_unpaid(db)


async def reconcile_payments() -> int:
    if (provider := optional_payment_provider()) is None:
        return 0
    async with SessionLocal() as db:
        return await payments.reconcile_processing(db, provider)


async def sync_shipments() -> int:
    """Polling fallback for tracking webhooks that never arrived."""
    if (provider := optional_shipping_provider()) is None:
        return 0
    async with SessionLocal() as db:
        return await shipping.sync_active(db, provider)


async def abandoned_carts() -> int:
    async with SessionLocal() as db:
        return await cart.queue_abandoned_cart_reminders(db)


async def cleanup() -> int:
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        removed = await cart.delete_stale_guest_carts(db)
        for stmt in (
            delete(UserToken).where(UserToken.expires_at < now - timedelta(days=7)),
            delete(UserSession).where(
                or_(UserSession.expires_at < now, UserSession.revoked_at < now - timedelta(days=30))
            ),
            delete(WebhookEvent).where(
                WebhookEvent.status.in_([WebhookStatus.PROCESSED, WebhookStatus.IGNORED]),
                WebhookEvent.received_at < now - timedelta(days=90),
            ),
        ):
            removed += (await db.execute(stmt)).rowcount  # type: ignore[attr-defined]
        await db.commit()
    return removed


async def reindex_search() -> int:
    async with SessionLocal() as db:
        return await reindex_all(db)
