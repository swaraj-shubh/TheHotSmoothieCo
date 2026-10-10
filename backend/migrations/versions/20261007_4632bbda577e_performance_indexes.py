"""performance indexes

Revision ID: 4632bbda577e
Revises: f0a434f945ce
Create Date: 2026-10-07 17:11:34.696209

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4632bbda577e"
down_revision: str | Sequence[str] | None = "f0a434f945ce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # CONCURRENTLY: builds without blocking writes on live tables (must run outside a transaction).
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_orders_customer_email",
            "orders",
            ["customer_email"],
            unique=False,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_orders_paid_at",
            "orders",
            ["paid_at"],
            unique=False,
            postgresql_where=sa.text("paid_at IS NOT NULL"),
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_users_email_trgm",
            "users",
            ["email"],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={"email": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_users_full_name_trgm",
            "users",
            ["full_name"],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={"full_name": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_users_phone_trgm",
            "users",
            ["phone"],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={"phone": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_users_phone_trgm",
            table_name="users",
            postgresql_using="gin",
            postgresql_ops={"phone": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_users_full_name_trgm",
            table_name="users",
            postgresql_using="gin",
            postgresql_ops={"full_name": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_users_email_trgm",
            table_name="users",
            postgresql_using="gin",
            postgresql_ops={"email": "gin_trgm_ops"},
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_orders_paid_at",
            table_name="orders",
            postgresql_where=sa.text("paid_at IS NOT NULL"),
            postgresql_concurrently=True,
        )
        op.drop_index("ix_orders_customer_email", table_name="orders", postgresql_concurrently=True)
