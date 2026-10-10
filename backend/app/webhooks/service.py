"""Generic inbound-webhook processing: dedupe, process once, record failures.

    INSERT event ON CONFLICT DO NOTHING
      new          -> process in this transaction; a concurrent duplicate blocks on the unique
                      index until we commit, then sees PROCESSED and stops
      seen, done   -> acknowledge (200) without doing anything
      seen, failed -> retry processing (gateways redeliver on non-2xx)

Handlers must also be idempotent on their own; this is the outer guard.
"""

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.payments.models import WebhookEvent, WebhookStatus

log = structlog.get_logger()


async def process(
    db: AsyncSession,
    provider: str,
    event_id: str,
    event_type: str,
    body: bytes,
    handler: Callable[[AsyncSession], Awaitable[bool]],
) -> str:
    """Returns the final status. Raises (-> 5xx, gateway retries) if the handler failed."""
    payload = json.loads(body)
    await db.execute(
        insert(WebhookEvent)
        .values(
            id=uuid.uuid4(),
            provider=provider,
            event_id=event_id[:128],
            event_type=event_type[:64],
            payload=payload,
            status=WebhookStatus.RECEIVED,
            attempts=0,
        )
        .on_conflict_do_nothing(constraint="uq_webhook_events_provider_event")
    )
    event = await db.scalar(
        select(WebhookEvent)
        .where(WebhookEvent.provider == provider, WebhookEvent.event_id == event_id[:128])
        .with_for_update()
    )
    assert event is not None
    if (status := event.status) in (WebhookStatus.PROCESSED, WebhookStatus.IGNORED):
        await db.rollback()  # expires `event`: read status before, never after
        log.info("webhook_duplicate", provider=provider, event_id=event_id)
        return status

    event.attempts += 1
    try:
        handled = await handler(db)
    except Exception as exc:
        await db.rollback()
        await _record_failure(provider, event_id, event_type, payload, exc)
        raise
    event.status = WebhookStatus.PROCESSED if handled else WebhookStatus.IGNORED
    event.processed_at = datetime.now(UTC)
    event.error = None
    await db.commit()
    log.info("webhook_processed", provider=provider, event_id=event_id, type=event_type, status=event.status)
    return event.status


async def _record_failure(
    provider: str, event_id: str, event_type: str, payload: dict, exc: Exception
) -> None:
    # Fresh session + upsert: the rollback above also discarded a brand-new event row.
    log.exception("webhook_failed", provider=provider, event_id=event_id, exc_info=exc)
    error = f"{type(exc).__name__}: {exc}"[:1000]
    async with SessionLocal() as s:
        await s.execute(
            insert(WebhookEvent)
            .values(
                id=uuid.uuid4(),
                provider=provider,
                event_id=event_id[:128],
                event_type=event_type[:64],
                payload=payload,
                status=WebhookStatus.FAILED,
                attempts=1,
                error=error,
            )
            .on_conflict_do_update(
                constraint="uq_webhook_events_provider_event",
                set_={"status": WebhookStatus.FAILED, "error": error, "attempts": WebhookEvent.attempts + 1},
            )
        )
        await s.commit()
