import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, status

from app.auth.dependencies import DB, CurrentUser
from app.auth.service import revoke_sessions
from app.users import service
from app.users.schemas import AddressIn, AddressOut, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(data: UserUpdate, user: CurrentUser, db: DB):
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, db: DB):
    # Soft delete: orders etc. keep their FK; the email is freed by the partial unique index.
    user.deleted_at = datetime.now(UTC)
    user.is_active = False
    await revoke_sessions(db, user.id)  # commits


@router.get("/me/addresses", response_model=list[AddressOut])
async def list_addresses(user: CurrentUser, db: DB):
    return await service.list_addresses(db, user.id)


@router.post("/me/addresses", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
async def create_address(data: AddressIn, user: CurrentUser, db: DB):
    return await service.create_address(db, user.id, data)


@router.put("/me/addresses/{address_id}", response_model=AddressOut)
async def replace_address(address_id: uuid.UUID, data: AddressIn, user: CurrentUser, db: DB):
    return await service.replace_address(db, user.id, address_id, data)


@router.delete("/me/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(address_id: uuid.UUID, user: CurrentUser, db: DB):
    await service.delete_address(db, user.id, address_id)
