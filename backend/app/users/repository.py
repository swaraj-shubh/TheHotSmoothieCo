import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import Role, User


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email.lower(), User.deleted_at.is_(None)))


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))


async def get_roles(db: AsyncSession, names: list[str]) -> list[Role]:
    return list(await db.scalars(select(Role).where(Role.name.in_(names))))
