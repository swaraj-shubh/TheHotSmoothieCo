import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Table, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Timestamps, UUIDPk


class RoleName(enum.StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    PRODUCT_MANAGER = "PRODUCT_MANAGER"
    INVENTORY_MANAGER = "INVENTORY_MANAGER"
    ORDER_MANAGER = "ORDER_MANAGER"
    CUSTOMER_SUPPORT = "CUSTOMER_SUPPORT"
    MARKETING_MANAGER = "MARKETING_MANAGER"


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(UUIDPk, Base):
    __tablename__ = "roles"
    name: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        # Partial unique index: a soft-deleted account frees its email for re-registration.
        Index("uq_users_email_active", "email", unique=True, postgresql_where=text("deleted_at IS NULL")),
        # Admin customer search uses ILIKE (prefix + infix): trigram indexes, not btree.
        *(
            Index(f"ix_users_{col}_trgm", col, postgresql_using="gin", postgresql_ops={col: "gin_trgm_ops"})
            for col in ("email", "full_name", "phone")
        ),
    )

    email: Mapped[str] = mapped_column(String(320))  # always stored lower-cased (see schemas)
    password_hash: Mapped[str | None] = mapped_column(String(255))  # null for future social-only logins
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    preferences: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin")

    @property
    def role_list(self) -> list[str]:
        return sorted(r.name for r in self.roles)

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None


class Address(UUIDPk, Timestamps, Base):
    """Orders snapshot the address at checkout, so editing/deleting here never changes past orders."""

    __tablename__ = "addresses"
    __table_args__ = (
        # At most one default of each kind per user, enforced by the database.
        Index(
            "uq_addresses_default_shipping",
            "user_id",
            unique=True,
            postgresql_where=text("is_default_shipping"),
        ),
        Index(
            "uq_addresses_default_billing",
            "user_id",
            unique=True,
            postgresql_where=text("is_default_billing"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    line1: Mapped[str] = mapped_column(String(255))
    line2: Mapped[str | None] = mapped_column(String(255))
    landmark: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    postal_code: Mapped[str] = mapped_column(String(12))
    country: Mapped[str] = mapped_column(String(2), server_default="IN")
    is_default_shipping: Mapped[bool] = mapped_column(server_default=text("false"))
    is_default_billing: Mapped[bool] = mapped_column(server_default=text("false"))
