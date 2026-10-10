import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFound
from app.users.models import Address
from app.users.schemas import AddressIn

MAX_ADDRESSES = 20


class AddressNotFound(NotFound):
    code, message = "ADDRESS_NOT_FOUND", "Address not found"


class AddressLimitReached(AppError):
    code, message = "ADDRESS_LIMIT_REACHED", f"You can save at most {MAX_ADDRESSES} addresses"


async def list_addresses(db: AsyncSession, user_id: uuid.UUID) -> list[Address]:
    return list(
        await db.scalars(select(Address).where(Address.user_id == user_id).order_by(Address.created_at))
    )


async def get_address(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> Address:
    # Scoped by user_id: one customer can never read or edit another's address (IDOR).
    address = await db.scalar(select(Address).where(Address.id == address_id, Address.user_id == user_id))
    if not address:
        raise AddressNotFound()
    return address


async def _clear_defaults(db: AsyncSession, user_id: uuid.UUID, data: AddressIn) -> None:
    # Unset the old default first; the partial unique indexes reject two defaults.
    if data.is_default_shipping:
        await db.execute(update(Address).where(Address.user_id == user_id).values(is_default_shipping=False))
    if data.is_default_billing:
        await db.execute(update(Address).where(Address.user_id == user_id).values(is_default_billing=False))


async def create_address(db: AsyncSession, user_id: uuid.UUID, data: AddressIn) -> Address:
    count = await db.scalar(select(func.count()).where(Address.user_id == user_id)) or 0
    if count >= MAX_ADDRESSES:
        raise AddressLimitReached()
    if count == 0:  # first address becomes the default for both
        data = data.model_copy(update={"is_default_shipping": True, "is_default_billing": True})
    await _clear_defaults(db, user_id, data)
    address = Address(user_id=user_id, **data.model_dump())
    db.add(address)
    await db.commit()
    return address


async def replace_address(
    db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID, data: AddressIn
) -> Address:
    address = await get_address(db, user_id, address_id)
    await _clear_defaults(db, user_id, data)
    # Un-ticking "default" on the current default is ignored: a user always keeps a default.
    values = data.model_dump()
    values["is_default_shipping"] = data.is_default_shipping or address.is_default_shipping
    values["is_default_billing"] = data.is_default_billing or address.is_default_billing
    for k, v in values.items():
        setattr(address, k, v)
    await db.commit()
    return address


async def delete_address(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
    address = await get_address(db, user_id, address_id)
    was_shipping, was_billing = address.is_default_shipping, address.is_default_billing
    await db.delete(address)
    await db.flush()
    if was_shipping or was_billing:  # promote the newest remaining address
        successor = await db.scalar(
            select(Address).where(Address.user_id == user_id).order_by(Address.created_at.desc()).limit(1)
        )
        if successor:
            successor.is_default_shipping = successor.is_default_shipping or was_shipping
            successor.is_default_billing = successor.is_default_billing or was_billing
    await db.commit()
