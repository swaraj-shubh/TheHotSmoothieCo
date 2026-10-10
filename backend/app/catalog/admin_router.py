import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.auth.dependencies import DB, require_roles
from app.catalog import service, taxonomy
from app.catalog.models import ProductStatus
from app.catalog.schemas import (
    AdminCategoryOut,
    AdminCollectionOut,
    AdminProductOut,
    AdminProductRow,
    AttributeIn,
    AttributeOut,
    AttributeValuesIn,
    CategoryIn,
    CategoryPatch,
    CollectionIn,
    CollectionPatch,
    MediaOut,
    MediaPatch,
    ProductIn,
    ProductPatch,
    VariantIn,
    VariantPatch,
)
from app.core.config import get_settings
from app.core.pagination import MAX_LIMIT, Page
from app.core.ratelimit import rate_limit
from app.media.storage import MAX_IMAGE_BYTES, InvalidUpload, MediaStorage, get_media_storage
from app.users.models import RoleName, User

router = APIRouter(
    prefix="/admin",
    tags=["admin: catalog"],
    dependencies=[Depends(rate_limit("admin", 300, 60))],
)
CatalogStaff = Annotated[User, Depends(require_roles(RoleName.ADMIN, RoleName.PRODUCT_MANAGER))]
Storage = Annotated[MediaStorage, Depends(get_media_storage)]


# ---------- Categories ----------


@router.get("/categories", response_model=list[AdminCategoryOut])
async def list_categories(_: CatalogStaff, db: DB):
    return await taxonomy.list_all_categories(db)


@router.post("/categories", response_model=AdminCategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(data: CategoryIn, _: CatalogStaff, db: DB):
    return await taxonomy.create_category(db, data)


@router.patch("/categories/{category_id}", response_model=AdminCategoryOut)
async def update_category(category_id: uuid.UUID, data: CategoryPatch, _: CatalogStaff, db: DB):
    return await taxonomy.update_category(db, category_id, data)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: uuid.UUID, _: CatalogStaff, db: DB):
    await taxonomy.delete_category(db, category_id)


# ---------- Collections ----------


@router.get("/collections", response_model=list[AdminCollectionOut])
async def list_collections(_: CatalogStaff, db: DB):
    return await taxonomy.list_all_collections(db)


@router.post("/collections", response_model=AdminCollectionOut, status_code=status.HTTP_201_CREATED)
async def create_collection(data: CollectionIn, _: CatalogStaff, db: DB):
    return await taxonomy.create_collection(db, data)


@router.patch("/collections/{collection_id}", response_model=AdminCollectionOut)
async def update_collection(collection_id: uuid.UUID, data: CollectionPatch, _: CatalogStaff, db: DB):
    return await taxonomy.update_collection(db, collection_id, data)


@router.delete("/collections/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collection(collection_id: uuid.UUID, _: CatalogStaff, db: DB):
    await taxonomy.delete_collection(db, collection_id)


# ---------- Attributes ----------


@router.get("/attributes", response_model=list[AttributeOut])
async def list_attributes(_: CatalogStaff, db: DB):
    return await taxonomy.list_attributes(db)


@router.post("/attributes", response_model=AttributeOut, status_code=status.HTTP_201_CREATED)
async def create_attribute(data: AttributeIn, _: CatalogStaff, db: DB):
    return await taxonomy.create_attribute(db, data)


@router.post("/attributes/{attribute_id}/values", response_model=AttributeOut)
async def add_attribute_values(attribute_id: uuid.UUID, data: AttributeValuesIn, _: CatalogStaff, db: DB):
    return await taxonomy.add_attribute_values(db, attribute_id, data.values)


# ---------- Products ----------


@router.get("/products", response_model=Page[AdminProductRow])
async def list_products(
    _: CatalogStaff,
    db: DB,
    status_: Annotated[ProductStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
):
    return await service.admin_list_products(db, status_, q, cursor, limit)


@router.post("/products", response_model=AdminProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(data: ProductIn, user: CatalogStaff, db: DB):
    return await service.create_product(db, data, user.id)


@router.get("/products/{product_id}", response_model=AdminProductOut)
async def get_product(product_id: uuid.UUID, _: CatalogStaff, db: DB):
    return await service.admin_product(db, product_id)


@router.patch("/products/{product_id}", response_model=AdminProductOut)
async def update_product(product_id: uuid.UUID, data: ProductPatch, _: CatalogStaff, db: DB):
    """Archive with `{"status": "ARCHIVED"}`. Products are never hard-deleted (orders reference them)."""
    return await service.update_product(db, product_id, data)


@router.post(
    "/products/{product_id}/variants", response_model=AdminProductOut, status_code=status.HTTP_201_CREATED
)
async def add_variant(product_id: uuid.UUID, data: VariantIn, user: CatalogStaff, db: DB):
    return await service.add_variant(db, product_id, data, user.id)


@router.patch("/products/{product_id}/variants/{variant_id}", response_model=AdminProductOut)
async def update_variant(
    product_id: uuid.UUID, variant_id: uuid.UUID, data: VariantPatch, _: CatalogStaff, db: DB
):
    return await service.update_variant(db, product_id, variant_id, data)


# ---------- Media ----------


@router.post("/products/{product_id}/media", response_model=MediaOut, status_code=status.HTTP_201_CREATED)
async def upload_media(
    product_id: uuid.UUID,
    _: CatalogStaff,
    db: DB,
    storage: Storage,
    file: Annotated[UploadFile, File()],
    alt_text: Annotated[str | None, Form(max_length=300)] = None,
    variant_id: Annotated[uuid.UUID | None, Form()] = None,
):
    data = await file.read(MAX_IMAGE_BYTES + 1)  # bounded read: never buffer more than the limit
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidUpload()
    return await service.add_media(
        db, storage, get_settings().media_folder, product_id, data, alt_text, variant_id
    )


@router.patch("/products/{product_id}/media/{media_id}", response_model=MediaOut)
async def update_media(product_id: uuid.UUID, media_id: uuid.UUID, data: MediaPatch, _: CatalogStaff, db: DB):
    return await service.update_media(db, product_id, media_id, data)


@router.delete("/products/{product_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(product_id: uuid.UUID, media_id: uuid.UUID, _: CatalogStaff, db: DB, storage: Storage):
    await service.delete_media(db, storage, product_id, media_id)
