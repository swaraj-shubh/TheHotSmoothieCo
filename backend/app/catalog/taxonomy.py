"""Categories, collections, tags and variant attributes."""

import re
import unicodedata
import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Attribute, AttributeValue, Category, Collection, Tag
from app.catalog.schemas import (
    AttributeIn,
    AttributeOut,
    CategoryIn,
    CategoryNode,
    CategoryPatch,
    CollectionIn,
    CollectionOut,
    CollectionPatch,
)
from app.core.cache import cached, invalidate
from app.core.exceptions import AppError, NotFound

CATEGORY_TREE_KEY = "cache:catalog:categories:v1"
COLLECTIONS_KEY = "cache:catalog:collections:v1"
CACHE_TTL = 3600


class CategoryNotFound(NotFound):
    code, message = "CATEGORY_NOT_FOUND", "Category not found"


class CollectionNotFound(NotFound):
    code, message = "COLLECTION_NOT_FOUND", "Collection not found"


class AttributeNotFound(NotFound):
    code, message = "ATTRIBUTE_NOT_FOUND", "Attribute not found"


def slugify(value: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")[:200] or uuid.uuid4().hex[:8]


async def _commit_and_invalidate(db: AsyncSession, *cache_keys: str) -> None:
    # Unique/FK violations propagate as IntegrityError and become SLUG_TAKEN / IN_USE (core.exceptions).
    await db.commit()
    await invalidate(*cache_keys)


# ---------- Categories ----------


async def category_tree(db: AsyncSession) -> list[dict]:
    """Active categories as a nested tree (cached). Children of an inactive category are hidden too."""

    async def load() -> list[dict]:
        rows = list(
            await db.scalars(
                select(Category)
                .where(Category.is_active.is_(True))
                .order_by(Category.sort_order, Category.name)
            )
        )
        nodes = {c.id: CategoryNode.model_validate(c).model_dump(mode="json") for c in rows}
        roots = []
        for c in rows:
            if c.parent_id is None:
                roots.append(nodes[c.id])
            elif c.parent_id in nodes:
                nodes[c.parent_id]["children"].append(nodes[c.id])
        return roots

    return await cached(CATEGORY_TREE_KEY, CACHE_TTL, load)


def _find(tree: list[dict], slug: str) -> dict | None:
    for node in tree:
        if node["slug"] == slug:
            return node
        if found := _find(node["children"], slug):
            return found
    return None


def _ids(node: dict) -> list[uuid.UUID]:
    return [uuid.UUID(node["id"]), *(i for child in node["children"] for i in _ids(child))]


async def category_by_slug(db: AsyncSession, slug: str) -> dict:
    node = _find(await category_tree(db), slug)
    if node is None:
        raise CategoryNotFound()
    return node


async def category_ids_with_descendants(db: AsyncSession, slug: str) -> list[uuid.UUID]:
    return _ids(await category_by_slug(db, slug))


async def _get_category(db: AsyncSession, category_id: uuid.UUID) -> Category:
    category = await db.get(Category, category_id)
    if category is None:
        raise CategoryNotFound()
    return category


async def _assert_no_cycle(db: AsyncSession, category_id: uuid.UUID, parent_id: uuid.UUID | None) -> None:
    seen = {category_id}
    while parent_id is not None:
        if parent_id in seen:
            raise AppError("A category cannot be nested inside itself", code="CATEGORY_CYCLE")
        seen.add(parent_id)
        parent_id = (await _get_category(db, parent_id)).parent_id


async def list_all_categories(db: AsyncSession) -> list[Category]:
    return list(await db.scalars(select(Category).order_by(Category.sort_order, Category.name).limit(1000)))


async def create_category(db: AsyncSession, data: CategoryIn) -> Category:
    if data.parent_id:
        await _get_category(db, data.parent_id)
    category = Category(**data.model_dump(exclude={"slug"}), slug=data.slug or slugify(data.name))
    db.add(category)
    await _commit_and_invalidate(db, CATEGORY_TREE_KEY)
    return category


async def update_category(db: AsyncSession, category_id: uuid.UUID, data: CategoryPatch) -> Category:
    category = await _get_category(db, category_id)
    changes = data.model_dump(exclude_unset=True)
    if "parent_id" in changes:
        await _assert_no_cycle(db, category_id, changes["parent_id"])
    for k, v in changes.items():
        setattr(category, k, v)
    await _commit_and_invalidate(db, CATEGORY_TREE_KEY)
    return category


async def delete_category(db: AsyncSession, category_id: uuid.UUID) -> None:
    await db.delete(await _get_category(db, category_id))
    await _commit_and_invalidate(db, CATEGORY_TREE_KEY)  # FK RESTRICT -> IN_USE if it has products/children


# ---------- Collections ----------


async def list_collections(db: AsyncSession) -> list[dict]:
    async def load() -> list[dict]:
        rows = await db.scalars(
            select(Collection)
            .where(Collection.is_active.is_(True))
            .order_by(Collection.sort_order, Collection.name)
        )
        return [CollectionOut.model_validate(c).model_dump(mode="json") for c in rows]

    return await cached(COLLECTIONS_KEY, CACHE_TTL, load)


async def collection_by_slug(db: AsyncSession, slug: str) -> Collection:
    c = await db.scalar(select(Collection).where(Collection.slug == slug, Collection.is_active.is_(True)))
    if c is None:
        raise CollectionNotFound()
    return c


async def get_collection(db: AsyncSession, collection_id: uuid.UUID) -> Collection:
    c = await db.get(Collection, collection_id)
    if c is None:
        raise CollectionNotFound()
    return c


async def list_all_collections(db: AsyncSession) -> list[Collection]:
    return list(
        await db.scalars(select(Collection).order_by(Collection.sort_order, Collection.name).limit(1000))
    )


async def create_collection(db: AsyncSession, data: CollectionIn) -> Collection:
    c = Collection(**data.model_dump(exclude={"slug"}), slug=data.slug or slugify(data.name))
    db.add(c)
    await _commit_and_invalidate(db, COLLECTIONS_KEY)
    return c


async def update_collection(db: AsyncSession, collection_id: uuid.UUID, data: CollectionPatch) -> Collection:
    c = await get_collection(db, collection_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    await _commit_and_invalidate(db, COLLECTIONS_KEY)
    return c


async def delete_collection(db: AsyncSession, collection_id: uuid.UUID) -> None:
    await db.delete(await get_collection(db, collection_id))  # product links cascade
    await _commit_and_invalidate(db, COLLECTIONS_KEY)


# ---------- Tags ----------


async def get_or_create_tags(db: AsyncSession, names: list[str]) -> list[Tag]:
    if not names:
        return []
    by_slug = {slugify(n): n for n in names}
    # ON CONFLICT DO NOTHING: two products created concurrently with the same new tag don't collide.
    await db.execute(
        insert(Tag)
        .values([{"id": uuid.uuid4(), "name": n, "slug": s} for s, n in by_slug.items()])
        .on_conflict_do_nothing(index_elements=["slug"])
    )
    return list(await db.scalars(select(Tag).where(Tag.slug.in_(by_slug))))


# ---------- Attributes ----------


ATTRIBUTES_KEY = "cache:catalog:attributes:v1"


async def public_attributes(db: AsyncSession) -> list[dict]:
    async def load() -> list[dict]:
        return [AttributeOut.model_validate(a).model_dump(mode="json") for a in await list_attributes(db)]

    return await cached(ATTRIBUTES_KEY, CACHE_TTL, load)


async def list_attributes(db: AsyncSession) -> list[Attribute]:
    return list(await db.scalars(select(Attribute).order_by(Attribute.sort_order, Attribute.name)))


async def _get_attribute(db: AsyncSession, attribute_id: uuid.UUID) -> Attribute:
    attribute = await db.get(Attribute, attribute_id)
    if attribute is None:
        raise AttributeNotFound()
    return attribute


async def create_attribute(db: AsyncSession, data: AttributeIn) -> Attribute:
    attribute = Attribute(code=data.code, name=data.name, sort_order=data.sort_order)
    db.add(attribute)
    await _commit_and_invalidate(db, ATTRIBUTES_KEY)
    return await add_attribute_values(db, attribute.id, data.values)


async def add_attribute_values(db: AsyncSession, attribute_id: uuid.UUID, values: list[str]) -> Attribute:
    await _get_attribute(db, attribute_id)
    if values:
        await resolve_attribute_values(db, attribute_id, values)
        await db.commit()
        await invalidate(ATTRIBUTES_KEY)
    db.expire_all()
    return await _get_attribute(db, attribute_id)


async def resolve_attribute_values(
    db: AsyncSession, attribute_id: uuid.UUID, values: list[str]
) -> dict[str, AttributeValue]:
    """Get-or-create values (by slug) for one attribute. Returns {slug: AttributeValue}."""
    by_slug = {slugify(v): v for v in values}
    if not by_slug:
        return {}
    start = (
        await db.scalar(
            select(func.max(AttributeValue.sort_order)).where(AttributeValue.attribute_id == attribute_id)
        )
        or 0
    )
    await db.execute(
        insert(AttributeValue)
        .values(
            [
                {
                    "id": uuid.uuid4(),
                    "attribute_id": attribute_id,
                    "value": v,
                    "slug": s,
                    "sort_order": start + i + 1,
                }
                for i, (s, v) in enumerate(by_slug.items())
            ]
        )
        .on_conflict_do_nothing(index_elements=["attribute_id", "slug"])
    )
    rows = await db.scalars(
        select(AttributeValue).where(
            AttributeValue.attribute_id == attribute_id, AttributeValue.slug.in_(by_slug)
        )
    )
    return {r.slug: r for r in rows}


async def attributes_by_code(db: AsyncSession, codes: set[str]) -> dict[str, Attribute]:
    rows = {a.code: a for a in await db.scalars(select(Attribute).where(Attribute.code.in_(codes)))}
    if missing := codes - rows.keys():
        raise AppError(
            "Unknown attribute(s); create them first", code="UNKNOWN_ATTRIBUTE", details=sorted(missing)
        )
    return rows
