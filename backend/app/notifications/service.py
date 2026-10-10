"""Notification outbox: enqueue inside business transactions, deliver from the worker.

Delivery is at-least-once: if a worker dies after the provider accepted an email but before the
row is marked SENT, the lease expires and it is sent again. For email that's the right trade-off
(a rare duplicate beats a lost order confirmation)."""

import asyncio
import random
import smtplib
import ssl
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import make_msgid
from string import Template
from typing import Protocol

import structlog
from sqlalchemy import select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError, NotFound
from app.core.pagination import Page, decode_cursor, encode_cursor
from app.notifications.models import Channel, Notification, NotificationStatus, NotificationTemplate
from app.notifications.templates import TEMPLATES, MessageTemplate, rupees

log = structlog.get_logger()

MAX_ATTEMPTS = 6  # ~30s, 1m, 2m, 4m, 8m between tries, then dead-letter
LEASE = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(UTC)


# ---------- Enqueue (called inside business transactions; never commits) ----------


async def enqueue(
    db: AsyncSession,
    template: str,
    *,
    recipient: str,
    context: dict,
    dedupe_key: str,
    user_id: uuid.UUID | None = None,
    channel: Channel = Channel.EMAIL,
) -> None:
    """Idempotent: the same dedupe_key is only ever queued once."""
    assert template in TEMPLATES, template
    await db.execute(
        insert(Notification)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            channel=channel,
            template=template,
            recipient=recipient,
            context=context,
            dedupe_key=dedupe_key[:200],
            status=NotificationStatus.PENDING,
            attempts=0,
        )
        .on_conflict_do_nothing(constraint="uq_notifications_dedupe_key")
    )


def order_context(order) -> dict:
    return {
        "name": order.customer_name.split(" ")[0],
        "order_number": order.number,
        "total": rupees(order.total_paise),
        "order_url": f"{get_settings().frontend_url}/account/orders/{order.id}",
    }


def add_order_notification(db: AsyncSession, order, template: str, extra: dict | None = None) -> None:
    """Sync variant for use inside orders.record_transition (no await available there). Each
    template fires at most once per order (the state machine guarantees it), so the key is stable."""
    db.add(
        Notification(
            user_id=order.user_id,
            channel=Channel.EMAIL,
            template=template,
            recipient=order.customer_email,
            context=order_context(order) | (extra or {}),
            dedupe_key=f"{template}:{order.id}",
            status=NotificationStatus.PENDING,
            attempts=0,
            next_attempt_at=_now(),
        )
    )


# ---------- Delivery ----------


class EmailSender(Protocol):
    async def send(self, to: str, subject: str, body: str) -> str | None: ...


class ConsoleEmailSender:
    """Development/test: logs instead of sending."""

    async def send(self, to: str, subject: str, body: str) -> str | None:
        log.info("email_console", to=to, subject=subject, body=body)
        return None


class SmtpEmailSender:
    """Any SMTP relay (SES, Brevo, Resend, Zoho, Gmail...): no vendor SDK, swap by config."""

    def __init__(self, host: str, port: int, username: str | None, password: str | None, sender: str):
        self.host, self.port, self.username, self.password, self.sender = (
            host,
            port,
            username,
            password,
            sender,
        )

    def _send_sync(self, msg: EmailMessage) -> None:
        context = ssl.create_default_context()
        if self.port == 465:
            server: smtplib.SMTP = smtplib.SMTP_SSL(self.host, self.port, timeout=20, context=context)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=20)
            server.starttls(context=context)
        with server:
            if self.username:
                server.login(self.username, self.password or "")
            server.send_message(msg)

    async def send(self, to: str, subject: str, body: str) -> str | None:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.sender, to, subject
        msg["Message-ID"] = make_msgid(domain=self.sender.rsplit("@", 1)[-1].strip(">"))
        msg.set_content(body)
        await asyncio.to_thread(self._send_sync, msg)  # smtplib blocks; keep the event loop free
        return msg["Message-ID"]


def get_email_sender() -> EmailSender:
    s = get_settings()
    if s.smtp_host:
        return SmtpEmailSender(
            s.smtp_host,
            s.smtp_port,
            s.smtp_username,
            s.smtp_password.get_secret_value() if s.smtp_password else None,
            s.email_from,
        )
    if s.environment in ("development", "test"):
        return ConsoleEmailSender()
    raise RuntimeError("SMTP_HOST is not configured")  # becomes a retry, then a dead letter


async def _template(db: AsyncSession, code: str, channel: str) -> MessageTemplate:
    built_in = TEMPLATES[code]
    override = await db.scalar(
        select(NotificationTemplate).where(
            NotificationTemplate.code == code,
            NotificationTemplate.channel == channel,
            NotificationTemplate.is_active.is_(True),
        )
    )
    if override is None:
        return built_in
    return MessageTemplate(override.subject, override.body, built_in.sensitive, built_in.marketing)


async def claim_due(batch: int = 50) -> list[uuid.UUID]:
    """Lease due rows to this worker. SKIP LOCKED + lease lets any number of workers drain safely,
    and a crashed worker's rows come back once the lease expires."""
    async with SessionLocal() as db:
        due = (
            select(Notification.id)
            .where(
                Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.SENDING]),
                Notification.next_attempt_at <= _now(),
            )
            .order_by(Notification.next_attempt_at)
            .limit(batch)
            .with_for_update(skip_locked=True)
        )
        rows = (
            await db.execute(
                update(Notification)
                .where(Notification.id.in_(due.scalar_subquery()))
                .values(status=NotificationStatus.SENDING, next_attempt_at=_now() + LEASE)
                .returning(Notification.id, Notification.created_at)
            )
        ).all()
        await db.commit()
    # RETURNING order is arbitrary: send oldest first so "confirmed" never arrives after "shipped".
    return [nid for nid, _ in sorted(rows, key=lambda r: r[1])]


async def deliver(notification_id: uuid.UUID, sender: EmailSender | None) -> str:
    async with SessionLocal() as db:
        n = await db.get(Notification, notification_id)
        if n is None or n.status != NotificationStatus.SENDING:
            return "gone"
        template = await _template(db, n.template, n.channel)
        try:
            if n.channel != Channel.EMAIL:
                n.status, n.last_error = NotificationStatus.SKIPPED, f"{n.channel} not enabled"
            elif template.marketing and await _opted_out(db, n.user_id):
                n.status, n.last_error = NotificationStatus.SKIPPED, "user opted out of marketing"
            else:
                if sender is None:
                    sender = get_email_sender()
                subject, body = template.render(n.context)
                n.provider_message_id = await sender.send(n.recipient, subject, body)
                n.status, n.subject, n.sent_at, n.last_error = (
                    NotificationStatus.SENT,
                    subject[:255],
                    _now(),
                    None,
                )
        except Exception as exc:  # any provider failure is retried; the worker itself never crashes
            n.attempts += 1
            n.last_error = f"{type(exc).__name__}: {exc}"[:1000]
            if n.attempts >= MAX_ATTEMPTS:
                n.status = NotificationStatus.FAILED
                log.error("notification_dead_letter", id=str(n.id), template=n.template, error=n.last_error)
            else:
                n.status = NotificationStatus.PENDING
                delay = min(30 * 2 ** (n.attempts - 1), 3600) * random.uniform(0.8, 1.2)  # noqa: S311 (jitter)
                n.next_attempt_at = _now() + timedelta(seconds=delay)
        if template.sensitive and n.status in (NotificationStatus.SENT, NotificationStatus.FAILED):
            n.context = {}  # don't keep live reset/verification tokens around
        await db.commit()
        return n.status


async def _opted_out(db: AsyncSession, user_id: uuid.UUID | None) -> bool:
    from app.users.models import User

    if user_id is None:
        return False
    user = await db.get(User, user_id)
    return user is None or user.preferences.get("marketing_emails") is False


async def drain(sender: EmailSender | None = None, batch: int = 50) -> int:
    ids = await claim_due(batch)
    for nid in ids:
        await deliver(nid, sender)
    return len(ids)


# ---------- Reads & admin ----------


class NotificationNotFound(NotFound):
    code, message = "NOTIFICATION_NOT_FOUND", "Notification not found"


async def list_notifications(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> Page:
    stmt = select(Notification)
    if user_id:
        stmt = stmt.where(Notification.user_id == user_id)
    if status:
        stmt = stmt.where(Notification.status == status)
    if cursor:
        ts, nid = decode_cursor(cursor, 2)
        stmt = stmt.where(
            tuple_(Notification.created_at, Notification.id) < (datetime.fromisoformat(ts), uuid.UUID(nid))
        )
    rows = list(
        await db.scalars(
            stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit + 1)
        )
    )
    page = rows[:limit]
    nxt = encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None
    return Page(items=page, next_cursor=nxt)


async def retry(db: AsyncSession, notification_id: uuid.UUID) -> Notification:
    n = await db.get(Notification, notification_id)
    if n is None:
        raise NotFound()
    if n.status != NotificationStatus.FAILED:
        raise AppError("Only failed notifications can be retried", code="NOT_RETRYABLE")
    if TEMPLATES[n.template].sensitive:
        raise AppError(
            "Expired security emails can't be resent; ask the customer to request a new one",
            code="NOT_RETRYABLE",
        )
    n.status, n.attempts, n.next_attempt_at = NotificationStatus.PENDING, 0, _now()
    await db.commit()
    return n


def allowed_placeholders(code: str) -> set[str]:
    t = TEMPLATES[code]
    return set(Template(t.subject).get_identifiers()) | set(Template(t.body).get_identifiers())


async def upsert_template(
    db: AsyncSession, code: str, subject: str, body: str, is_active: bool
) -> NotificationTemplate:
    if code not in TEMPLATES:
        raise NotFound("Unknown template", code="TEMPLATE_NOT_FOUND")
    used = set(Template(subject).get_identifiers()) | set(Template(body).get_identifiers())
    if unknown := used - allowed_placeholders(code):
        raise AppError(
            "Unknown placeholder(s) in template",
            code="INVALID_TEMPLATE",
            details={"unknown": sorted(unknown), "allowed": sorted(allowed_placeholders(code))},
        )
    await db.execute(
        insert(NotificationTemplate)
        .values(
            id=uuid.uuid4(), code=code, channel=Channel.EMAIL, subject=subject, body=body, is_active=is_active
        )
        .on_conflict_do_update(
            constraint="uq_notification_templates_code_channel",
            set_={"subject": subject, "body": body, "is_active": is_active, "updated_at": _now()},
        )
    )
    await db.commit()
    row = await db.scalar(
        select(NotificationTemplate)
        .where(NotificationTemplate.code == code, NotificationTemplate.channel == Channel.EMAIL)
        .execution_options(populate_existing=True)
    )
    assert row is not None
    return row
