import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk


class Channel(enum.StrEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    PUSH = "PUSH"


class NotificationStatus(enum.StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"  # claimed by a worker; lease expires at next_attempt_at
    SENT = "SENT"
    FAILED = "FAILED"  # gave up after max attempts: the dead-letter list
    SKIPPED = "SKIPPED"  # e.g. user opted out


class Notification(UUIDPk, Timestamps, Base):
    """Transactional outbox: written in the same DB transaction as the business change, delivered
    later by the worker. A crash can delay a notification but never lose it."""

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_notifications_dedupe_key"),
        # The worker's claim query: due, undelivered rows.
        Index(
            "ix_notifications_due",
            "next_attempt_at",
            postgresql_where=text("status IN ('PENDING', 'SENDING')"),
        ),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(16))
    template: Mapped[str] = mapped_column(String(64))
    recipient: Mapped[str] = mapped_column(String(320))
    context: Mapped[dict] = mapped_column(JSONB)  # cleared after sending for sensitive templates
    dedupe_key: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), index=True)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(String(1000))
    subject: Mapped[str | None] = mapped_column(String(255))  # rendered, kept for the customer's history
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(255))


class NotificationTemplate(UUIDPk, Timestamps, Base):
    """Optional staff-edited override of a built-in template (app.notifications.templates)."""

    __tablename__ = "notification_templates"
    __table_args__ = (UniqueConstraint("code", "channel", name="uq_notification_templates_code_channel"),)

    code: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(16))
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
