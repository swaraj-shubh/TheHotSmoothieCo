"""Seed a small, realistic demo catalog for local development / frontend work.

    python -m scripts.seed_demo

Idempotent (skips anything that already exists). Uses the real service layer, so every business
rule applies. Never run against production.

If Cloudinary is configured, products without images get SEED_IMAGE (sampleImage/a_31.webp) uploaded.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

import app.models  # noqa: F401  (register every model before using any)
from app.catalog import service, taxonomy
from app.catalog.models import Attribute, Category, Collection, Product, ProductMedia
from app.catalog.schemas import AttributeIn, CategoryIn, CollectionIn, ProductIn, VariantIn
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.coupons.models import Coupon
from app.coupons.schemas import CouponIn
from app.coupons.service import create as create_coupon
from app.media.storage import MediaStorageUnavailable, get_media_storage

ATTRIBUTES = [
    ("size", "Size", 0, ["A5", "A4", "A3", "A2"]),
    ("frame", "Frame", 1, ["No Frame", "Black", "White", "Oak"]),
    ("paper", "Paper", 2, ["Matte", "Glossy"]),
]
CATEGORIES = [
    ("Posters", None),
    ("Movie Posters", "posters"),
    ("Music Posters", "posters"),
    ("Travel Prints", "posters"),
    ("Stickers", None),
    ("Framed Art", None),
]
# ponytail: one image shared by every demo product; give each its own file when it matters.
SEED_IMAGE = Path(__file__).resolve().parents[2] / "sampleImage" / "a_31.webp"
COLLECTIONS = ["Monsoon Moods", "Retro Bollywood", "Minimal Lines", "Bestsellers"]
# Prices in rupees. A3 framed costs more than A4 unframed, as you'd expect.
POSTER_SIZES = {"A4": 499, "A3": 799, "A2": 1199}
FRAME_EXTRA = {"No Frame": 0, "Black": 700, "White": 700}
PRODUCTS = [
    (
        "Monsoon Over Marine Drive",
        "travel-prints",
        ["monsoon-moods", "bestsellers"],
        ["mumbai", "rain"],
        "Mumbai's queen's necklace, blurred by the first rains.",
    ),
    (
        "Neon Chai Stall",
        "posters",
        ["minimal-lines"],
        ["neon", "street"],
        "A late-night tapri glowing in pink and teal.",
    ),
    (
        "Sholay Reimagined",
        "movie-posters",
        ["retro-bollywood", "bestsellers"],
        ["bollywood", "classic"],
        "The 1975 classic as a bold two-colour screenprint.",
    ),
    (
        "Coke Studio Waves",
        "music-posters",
        ["minimal-lines"],
        ["music", "abstract"],
        "Sound waves from a favourite session, drawn as ink lines.",
    ),
    (
        "Hampi Boulders at Dusk",
        "travel-prints",
        ["monsoon-moods"],
        ["karnataka", "heritage"],
        "Granite giants under a tangerine sky.",
    ),
    (
        "The Crocodile Sips",
        "posters",
        ["bestsellers"],
        ["mascot", "fun"],
        "Our mascot, mid-smoothie. Obviously.",
    ),
    (
        "Mughal-e-Azam Gold",
        "movie-posters",
        ["retro-bollywood"],
        ["bollywood", "gold"],
        "Gilded linework inspired by the 1960 epic.",
    ),
    (
        "Ladakh Line Study",
        "travel-prints",
        ["minimal-lines"],
        ["ladakh", "mountains"],
        "Twelve lines, one horizon.",
    ),
]


async def exists(db, model, field: str, value: str) -> bool:
    return await db.scalar(select(model.id).where(getattr(model, field) == value)) is not None


def poster_variants(index: int, title: str) -> list[VariantIn]:
    code = "".join(w[0] for w in title.split()).upper()
    return [
        VariantIn(
            sku=f"{code}-{size}-{frame.split()[0][:3].upper()}",
            price_paise=(base + FRAME_EXTRA[frame]) * 100,
            compare_at_price_paise=(base + FRAME_EXTRA[frame] + 200) * 100 if index % 3 == 0 else None,
            weight_grams=250 if frame == "No Frame" else 1200,
            attributes={"size": size, "frame": frame},
            initial_stock=0 if (index == 4 and size == "A2") else 5 + (index * 7 + len(size)) % 20,
            low_stock_threshold=3,
        )
        for size, base in POSTER_SIZES.items()
        for frame in FRAME_EXTRA
    ]


async def seed_images(db) -> None:
    try:
        storage = get_media_storage()
    except MediaStorageUnavailable:
        print("Cloudinary not configured: skipping product images.")
        return
    if not SEED_IMAGE.is_file():
        print(f"{SEED_IMAGE} not found: skipping product images.")
        return
    data = SEED_IMAGE.read_bytes()
    slugs = [taxonomy.slugify(p[0]) for p in PRODUCTS]
    without_media = await db.execute(
        select(Product.id, Product.title).where(
            Product.slug.in_(slugs), ~Product.id.in_(select(ProductMedia.product_id))
        )
    )
    for product_id, title in without_media.all():
        await service.add_media(db, storage, get_settings().media_folder, product_id, data, title, None)
        print(f"Uploaded image for {title}")


async def main() -> None:
    if get_settings().is_production:
        sys.exit("Refusing to seed demo data into production")
    async with SessionLocal() as db:
        for code, name, order, values in ATTRIBUTES:
            if not await exists(db, Attribute, "code", code):
                await taxonomy.create_attribute(
                    db, AttributeIn(code=code, name=name, sort_order=order, values=values)
                )
        for name, parent_slug in CATEGORIES:
            if not await exists(db, Category, "slug", taxonomy.slugify(name)):
                parent = (
                    await db.scalar(select(Category.id).where(Category.slug == parent_slug))
                    if parent_slug
                    else None
                )
                await taxonomy.create_category(db, CategoryIn(name=name, parent_id=parent))
        for name in COLLECTIONS:
            if not await exists(db, Collection, "slug", taxonomy.slugify(name)):
                await taxonomy.create_collection(db, CollectionIn(name=name))

        cats = dict((await db.execute(select(Category.slug, Category.id))).all())
        cols = dict((await db.execute(select(Collection.slug, Collection.id))).all())
        for i, (title, cat, collections, tags, blurb) in enumerate(PRODUCTS):
            slug = taxonomy.slugify(title)
            if await exists(db, Product, "slug", slug):
                continue
            product = ProductIn(
                title=title,
                slug=slug,
                status="ACTIVE",
                category_id=cats[cat],
                short_description=blurb,
                description=f"{blurb}\n\nPrinted on 250 gsm archival paper with fade-resistant inks.",
                collection_ids=[cols[c] for c in collections],
                tags=tags,
                variants=poster_variants(i, title),
            )
            await service.create_product(db, product, None)

        await seed_images(db)

        if not await exists(db, Coupon, "code", "WELCOME10"):
            await create_coupon(
                db,
                CouponIn(
                    code="WELCOME10",
                    discount_type="PERCENT",
                    value=10,
                    max_discount_paise=30000,
                    first_order_only=True,
                    description="10% off your first order (up to ₹300)",
                ),
            )
        count = len(list(await db.scalars(select(Product.id))))
    print(f"Demo catalog ready: {count} products. Try GET /api/v1/products and coupon WELCOME10.")


if __name__ == "__main__":
    asyncio.run(main())
