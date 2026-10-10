"""Seed one real product with real photos: "Mahadev & Nandi Under the Moon".

    python -m scripts.seed_demo2

Run scripts.seed_demo first (it creates the size/frame attributes, categories and collections).
Idempotent: skips the product if it exists and only uploads photos it doesn't have yet. Images are
read from ../sampleImage and uploaded to Cloudinary. Never run against production.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select

import app.models  # noqa: F401  (register every model before using any)
from app.catalog import service
from app.catalog.models import Category, Collection, Product, ProductMedia
from app.catalog.schemas import ProductIn, VariantIn
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.media.storage import MediaStorageUnavailable, get_media_storage

IMAGES_DIR = Path(__file__).resolve().parents[2] / "sampleImage"
SLUG = "mahadev-nandi-under-the-moon"
# (file, alt text) in gallery order: the first is the cover image.
IMAGES = [
    (
        "Mystical Shiva in Moonlit Serenity.png",
        "Mahadev and Nandi framed print in a black frame on a white brick wall",
    ),
    (
        "Shiva and Nandi Beneath the Moon.png",
        "Full artwork: Mahadev with trishul and damru beside Nandi, under a glowing moon",
    ),
    ("Angled Shiva Moonlight Wall Art.png", "Side view of the framed print showing the black frame depth"),
    ("Cinematic Shiva Art Bedroom Retreat.png", "The framed print hung above a bed in a warmly lit bedroom"),
]
# Rupees: (unframed, black frame) per size.
PRICES = {"A4": (599, 1299), "A3": (899, 1799), "A2": (1399, 2499)}

DESCRIPTION = """\
Mahadev in deep meditation, eyes closed, the crescent moon in his jata and Vasuki coiled at his \
shoulder. His trishul and damru rise beside him, Nandi rests at his side, and a temple glows on the \
peaks of Kailash beneath a full golden moon.

Rich blacks and warm gold make this a calm, powerful piece for a pooja room, living room or bedroom.

- Printed on 250 gsm archival matte paper with fade-resistant inks
- Black frame: matte black wood-finish frame with a shatter-resistant acrylic front, ready to hang
- Unframed prints ship rolled in a rigid tube
- Sizes: A4 (21 × 29.7 cm), A3 (29.7 × 42 cm), A2 (42 × 59.4 cm)"""

PRODUCT = ProductIn(
    title="Mahadev & Nandi Under the Moon",
    slug=SLUG,
    status="ACTIVE",
    short_description="Mahadev in meditation with Nandi, trishul and damru, beneath a glowing full moon.",
    description=DESCRIPTION,
    seo_title="Mahadev & Nandi Under the Moon | Framed Shiva Wall Art",
    seo_description="Lord Shiva and Nandi beneath the moon, printed on 250 gsm archival paper. "
    "Available unframed or in a black frame, in A4, A3 and A2.",
    tags=["mahadev", "shiva", "nandi", "spiritual", "devotional"],
    variants=[
        VariantIn(
            sku=f"MNM-{size}-{'BLA' if framed else 'NO'}",
            price_paise=price * 100,
            # Launch offer on framed sizes.
            compare_at_price_paise=(price + 400) * 100 if framed else None,
            weight_grams=1200 if framed else 250,
            attributes={"size": size, "frame": "Black" if framed else "No Frame"},
            initial_stock=12 if framed else 25,
            low_stock_threshold=3,
        )
        for size, prices in PRICES.items()
        for framed, price in enumerate(prices)
    ],
)


async def main() -> None:
    settings = get_settings()
    if settings.is_production:
        sys.exit("Refusing to seed demo data into production")
    try:
        storage = get_media_storage()
    except MediaStorageUnavailable:
        sys.exit("Cloudinary is not configured (CLOUDINARY_* in .env)")
    missing = [f for f, _ in IMAGES if not (IMAGES_DIR / f).is_file()]
    if missing:
        sys.exit(f"Missing images in {IMAGES_DIR}: {missing}")

    async with SessionLocal() as db:
        category = await db.scalar(select(Category.id).where(Category.slug == "framed-art"))
        if category is None:
            sys.exit("Run `python -m scripts.seed_demo` first (categories and attributes)")

        product_id = await db.scalar(select(Product.id).where(Product.slug == SLUG))
        if product_id is None:
            collections = await db.scalars(select(Collection.id).where(Collection.slug == "bestsellers"))
            data = PRODUCT.model_copy(update={"category_id": category, "collection_ids": list(collections)})
            product_id = (await service.create_product(db, data, None)).id
            print(f"Created {PRODUCT.title}")

        # Resume where a previous (interrupted) run stopped.
        have = await db.scalar(select(func.count()).where(ProductMedia.product_id == product_id))
        for file, alt in IMAGES[have:]:
            await service.add_media(
                db, storage, settings.media_folder, product_id, (IMAGES_DIR / file).read_bytes(), alt, None
            )
            print(f"Uploaded {file}")
    print(f"Done: /product/{SLUG}")


if __name__ == "__main__":
    asyncio.run(main())
