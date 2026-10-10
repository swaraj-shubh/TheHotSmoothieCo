import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPk


class AuditLog(UUIDPk, Base):
    """Append-only record of every state-changing admin request — including denied and failed
    ones. Actor details are snapshotted so the log stays meaningful after accounts change."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_logs_target", "target_id"),
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_email: Mapped[str | None] = mapped_column(String(320))
    actor_roles: Mapped[list | None] = mapped_column(JSONB)
    action: Mapped[str] = mapped_column(String(200))  # "PATCH /api/v1/admin/products/{product_id}"
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    status_code: Mapped[int] = mapped_column(Integer)
    target_type: Mapped[str | None] = mapped_column(String(60))
    target_id: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    request_body: Mapped[dict | None] = mapped_column(JSONB)  # secrets redacted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
