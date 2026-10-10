import enum
from datetime import datetime

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk


class BannerPlacement(enum.StrEnum):
    HOME_HERO = "HOME_HERO"
    HOME_STRIP = "HOME_STRIP"
    SHOP_TOP = "SHOP_TOP"


class Banner(UUIDPk, Timestamps, Base):
    """Merchandising banners for the storefront, optionally scheduled (sale starts/ends)."""

    __tablename__ = "banners"
    __table_args__ = (Index("ix_banners_placement_active", "placement", postgresql_where=text("is_active")),)

    title: Mapped[str] = mapped_column(String(120))
    subtitle: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str] = mapped_column(String(1024))
    mobile_image_url: Mapped[str | None] = mapped_column(String(1024))
    link_url: Mapped[str | None] = mapped_column(String(1024))
    placement: Mapped[str] = mapped_column(String(20))
    sort_order: Mapped[int] = mapped_column(server_default="0")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))
