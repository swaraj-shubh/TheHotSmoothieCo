"""Bulk product CSV import/export. One row per variant.

Columns: product_slug, product_title, status, category_slug, collections (slug|slug), tags (a|b),
short_description, sku, options ("size=A3; frame=Black"), price (rupees, e.g. 1499.00),
compare_at_price, weight_grams, on_hand, low_stock_threshold, variant_active (true/false).

Import is all-or-nothing and goes through the same service rules as the admin API (variant
combination checks, price rules, search indexing, inventory ledger). Blank optional cells leave
existing values unchanged. `dry_run=true` validates and reports without saving anything.
"""

import csv
import io
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import repository as repo
from app.catalog import service
from app.catalog.models import Category, Collection, Product, ProductStatus, ProductVariant
from app.catalog.schemas import ProductIn, ProductPatch, VariantIn, VariantPatch
from app.core.exceptions import AppError
from app.inventory import service as inventory
from app.inventory.models import Inventory

COLUMNS = [
    "product_slug",
    "product_title",
    "status",
    "category_slug",
    "collections",
    "tags",
    "short_description",
    "sku",
    "options",
    "price",
    "compare_at_price",
    "weight_grams",
    "on_hand",
    "low_stock_threshold",
    "variant_active",
]
REQUIRED = {"product_slug", "product_title", "sku", "price"}
MAX_ROWS = 5000
MAX_BYTES = 5 * 1024 * 1024
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class InvalidCsv(AppError):
    code, message = "INVALID_CSV", "The CSV file has errors; nothing was imported"


# ---------- Export ----------


def _safe(value: object) -> str:
    """Neutralise spreadsheet formula injection (=HYPERLINK(...) in a product title, etc.)."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(FORMULA_PREFIXES) else text


def _rupees(paise: int | None) -> str:
    return "" if paise is None else f"{Decimal(paise) / 100:.2f}"


async def export_rows(db: AsyncSession, batch: int = 100) -> AsyncIterator[str]:
    """Streams the whole catalog with bounded memory (keyset batches)."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    def flush() -> str:
        out = buf.getvalue()
        buf.seek(0)
        buf.truncate()
        return out

    writer.writerow(COLUMNS)
    yield flush()
    last_id: uuid.UUID | None = None
    while True:
        stmt = repo.product_query().order_by(Product.id).limit(batch)
        if last_id:
            stmt = stmt.where(Product.id > last_id)
        products = list(await db.scalars(stmt))
        if not products:
            return
        variant_ids = [v.id for p in products for v in p.variants]
        stock = {
            i.variant_id: i
            for i in await db.scalars(select(Inventory).where(Inventory.variant_id.in_(variant_ids)))
        }
        for p in products:
            for v in p.variants:
                inv = stock.get(v.id)
                writer.writerow(
                    [
                        _safe(x)
                        for x in (
                            p.slug,
                            p.title,
                            p.status,
                            p.category.slug if p.category else "",
                            "|".join(c.slug for c in p.collections),
                            "|".join(t.name for t in p.tags),
                            p.short_description or "",
                            v.sku,
                            "; ".join(f"{k}={val}" for k, val in v.attributes.items()),
                            _rupees(v.price_paise),
                            _rupees(v.compare_at_price_paise),
                            v.weight_grams or "",
                            inv.on_hand if inv else 0,
                            inv.low_stock_threshold if inv else "",
                            str(v.is_active).lower(),
                        )
                    ]
                )
        yield flush()
        last_id = products[-1].id
        db.expunge_all()


# ---------- Import ----------


@dataclass
class ImportReport:
    dry_run: bool
    rows: int = 0
    products_created: int = 0
    products_updated: int = 0
    variants_created: int = 0
    variants_updated: int = 0
    stock_adjusted: int = 0
    errors: list[dict] = field(default_factory=list)


@dataclass
class Row:
    line: int
    cells: dict[str, str]
    variant: VariantIn
    on_hand: int | None
    active: bool | None


def _cell(cells: dict, key: str) -> str:
    value = (cells.get(key) or "").strip()
    if value.startswith("'") and value[1:].startswith(FORMULA_PREFIXES):
        value = value[1:]  # undo our own export escaping
    return value


def _paise(value: str, column: str) -> int | None:
    if not value:
        return None
    try:
        d = Decimal(value.replace(",", "").replace("₹", ""))
    except InvalidOperation as exc:
        raise ValueError(f"{column}: '{value}' is not a number") from exc
    if d.as_tuple().exponent < -2:  # type: ignore[operator]
        raise ValueError(f"{column}: at most 2 decimal places")
    return int(d * 100)


def _int(value: str, column: str) -> int | None:
    if not value:
        return None
    if not value.isdigit():
        raise ValueError(f"{column}: '{value}' must be a whole number")
    return int(value)


def _options(value: str) -> dict[str, str]:
    out = {}
    for part in filter(None, (p.strip() for p in value.split(";"))):
        key, sep, val = part.partition("=")
        if not sep or not key.strip() or not val.strip():
            raise ValueError(f"options: '{part}' should look like size=A3")
        out[key.strip().lower()] = val.strip()
    return out


def _parse(data: bytes, report: ImportReport) -> list[Row]:
    if len(data) > MAX_BYTES:
        raise InvalidCsv(f"File is larger than {MAX_BYTES // (1024 * 1024)} MB")
    try:
        text = data.decode("utf-8-sig")  # Excel adds a BOM
    except UnicodeDecodeError as exc:
        raise InvalidCsv("File must be UTF-8 encoded CSV") from exc
    reader = csv.DictReader(io.StringIO(text))
    headers = {h.strip() for h in reader.fieldnames or []}
    if missing := REQUIRED - headers:
        raise InvalidCsv(details={"missing_columns": sorted(missing)})

    rows: list[Row] = []
    for line, raw in enumerate(reader, start=2):  # line 1 is the header
        report.rows += 1
        if report.rows > MAX_ROWS:
            raise InvalidCsv(f"At most {MAX_ROWS} rows per import")
        cells = {k.strip(): v for k, v in raw.items() if k}
        try:
            low = _int(_cell(cells, "low_stock_threshold"), "low_stock_threshold")
            active = _cell(cells, "variant_active").lower()
            if active not in ("", "true", "false"):
                raise ValueError("variant_active: use true or false")
            variant = VariantIn(
                sku=_cell(cells, "sku"),
                price_paise=_paise(_cell(cells, "price"), "price"),
                compare_at_price_paise=_paise(_cell(cells, "compare_at_price"), "compare_at_price"),
                weight_grams=_int(_cell(cells, "weight_grams"), "weight_grams"),
                attributes=_options(_cell(cells, "options")),
                initial_stock=_int(_cell(cells, "on_hand"), "on_hand") or 0,
                low_stock_threshold=5 if low is None else low,
            )
            if not _cell(cells, "product_slug") or not _cell(cells, "product_title"):
                raise ValueError("product_slug and product_title are required")
            rows.append(
                Row(
                    line,
                    cells,
                    variant,
                    _int(_cell(cells, "on_hand"), "on_hand"),
                    active == "true" if active else None,
                )
            )
        except ValidationError as exc:
            report.errors += [
                {"row": line, "error": f"{'.'.join(map(str, e['loc']))}: {e['msg']}"} for e in exc.errors()
            ]
        except ValueError as exc:
            report.errors.append({"row": line, "error": str(exc)})
    skus = [r.variant.sku for r in rows]
    for dup in {s for s in skus if skus.count(s) > 1}:
        report.errors.append(
            {
                "row": next(r.line for r in rows if r.variant.sku == dup),
                "error": f"SKU {dup} appears more than once",
            }
        )
    return rows


async def _lookup(db: AsyncSession, model, slugs: set[str]) -> dict[str, uuid.UUID]:
    if not slugs:
        return {}
    return dict((await db.execute(select(model.slug, model.id).where(model.slug.in_(slugs)))).all())


def _split(value: str) -> list[str]:
    return [v.strip() for v in value.split("|") if v.strip()]


async def _apply_group(
    db: AsyncSession,
    slug: str,
    rows: list[Row],
    categories,
    collections,
    existing_skus,
    actor_id,
    report: ImportReport,
) -> None:
    first = rows[0].cells
    status = _cell(first, "status").upper()
    if status and status not in ProductStatus.__members__:
        raise ValueError(f"status must be one of {', '.join(ProductStatus)}")
    cat_slug = _cell(first, "category_slug")
    if cat_slug and cat_slug not in categories:
        raise ValueError(f"unknown category_slug '{cat_slug}'")
    col_slugs = _split(_cell(first, "collections"))
    if unknown := [c for c in col_slugs if c not in collections]:
        raise ValueError(f"unknown collections: {', '.join(unknown)}")

    product_id = await db.scalar(select(Product.id).where(Product.slug == slug))
    for r in rows:
        owner = existing_skus.get(r.variant.sku)
        if owner and owner[1] != product_id:
            raise ValueError(f"SKU {r.variant.sku} already belongs to another product")

    fields = {
        "title": _cell(first, "product_title"),
        "short_description": _cell(first, "short_description") or None,
        "category_id": categories.get(cat_slug) if cat_slug else None,
    }
    tags = _split(_cell(first, "tags")) if "tags" in first else None
    collection_ids = [collections[c] for c in col_slugs] if "collections" in first else None

    if product_id is None:
        await service.stage_create_product(
            db,
            ProductIn(
                slug=slug,
                status=status or ProductStatus.DRAFT,
                variants=[r.variant for r in rows],
                tags=tags or [],
                collection_ids=collection_ids or [],
                **fields,
            ),
            actor_id,
        )
        report.products_created += 1
        report.variants_created += len(rows)
        return

    patch = {k: v for k, v in fields.items() if v is not None}
    if tags is not None and _cell(first, "tags"):
        patch["tags"] = tags
    if collection_ids is not None and col_slugs:
        patch["collection_ids"] = collection_ids
    await service.stage_update_product(db, product_id, ProductPatch(**patch))
    report.products_updated += 1
    for r in rows:
        if owner := existing_skus.get(r.variant.sku):
            variant_id = owner[0]
            current = await db.get(ProductVariant, variant_id)
            assert current is not None
            if r.variant.attributes and r.variant.attributes != current.attributes:
                raise ValueError(
                    f"options of existing SKU {r.variant.sku} can't change; add a new SKU instead"
                )
            changes = {"price_paise": r.variant.price_paise}
            if r.variant.compare_at_price_paise is not None:
                changes["compare_at_price_paise"] = r.variant.compare_at_price_paise
            if r.variant.weight_grams is not None:
                changes["weight_grams"] = r.variant.weight_grams
            if r.active is not None:
                changes["is_active"] = r.active
            await service.stage_update_variant(db, product_id, variant_id, VariantPatch(**changes))
            report.variants_updated += 1
            if r.on_hand is not None:
                inv = await db.get(Inventory, variant_id)
                if inv is None or inv.on_hand != r.on_hand:
                    await inventory.adjust(
                        db, variant_id, set_to=r.on_hand, reason="CSV import", actor_id=actor_id
                    )
                    report.stock_adjusted += 1
        else:
            await service.stage_add_variant(db, product_id, r.variant, actor_id)
            report.variants_created += 1
    if status:
        await service.stage_update_product(db, product_id, ProductPatch(status=ProductStatus(status)))


async def import_csv(db: AsyncSession, data: bytes, actor_id: uuid.UUID, dry_run: bool) -> ImportReport:
    report = ImportReport(dry_run=dry_run)
    rows = _parse(data, report)
    if report.errors:
        raise InvalidCsv(details=asdict(report))

    groups: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        groups[_cell(r.cells, "product_slug").lower()].append(r)
    categories = await _lookup(
        db, Category, {_cell(g[0].cells, "category_slug") for g in groups.values()} - {""}
    )
    collections = await _lookup(
        db, Collection, {c for g in groups.values() for c in _split(_cell(g[0].cells, "collections"))}
    )
    existing_skus = {
        sku: (vid, pid)
        for sku, vid, pid in (
            await db.execute(
                select(ProductVariant.sku, ProductVariant.id, ProductVariant.product_id).where(
                    ProductVariant.sku.in_([r.variant.sku for r in rows])
                )
            )
        ).all()
    }

    for slug, group in groups.items():
        try:
            async with db.begin_nested():  # a failing product rolls back alone so we can report them all
                await _apply_group(db, slug, group, categories, collections, existing_skus, actor_id, report)
        except (AppError, ValueError) as exc:
            msg = exc.message if isinstance(exc, AppError) else str(exc)
            report.errors.append({"row": group[0].line, "product_slug": slug, "error": msg})

    if report.errors:
        await db.rollback()
        raise InvalidCsv(details=asdict(report))
    if dry_run:
        await db.rollback()
    else:
        await db.commit()
    return report
