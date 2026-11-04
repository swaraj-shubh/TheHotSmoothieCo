"""Load the catalogue of the designed storefront (site/): 3 collections, 5 posters, their photos.

    python -m scripts.seed_site                # add it
    python -m scripts.seed_site --archive-demo # also hide what scripts.seed_demo created

Copy, sizes and prices come from site/js/data.js. Images are uploaded to Cloudinary
from frontend/public/assets.
Idempotent: skips what exists and only uploads photos a product doesn't have yet. Uses the real
service layer. Never run against production without confirming the placeholder prices first.
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select, update

import app.models  # noqa: F401  (register every model before using any)
from app.catalog import service, taxonomy
from app.catalog.models import Attribute, Collection, Product, ProductMedia, ProductStatus
from app.catalog.schemas import AttributeIn, CollectionIn, ProductIn, VariantIn
from app.core.cache import invalidate
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.coupons.models import Coupon
from app.coupons.schemas import CouponIn
from app.coupons.service import create as create_coupon
from app.media.storage import MediaStorageUnavailable, get_media_storage
from scripts.seed_demo import COLLECTIONS as DEMO_COLLECTIONS
from scripts.seed_demo import PRODUCTS as DEMO_PRODUCTS

ASSETS = Path(__file__).resolve().parents[2] / "frontend" / "public" / "assets"

# (size, price in rupees, width mm, height mm)
SIZES = [("A4", 499, 210, 297), ("A3", 799, 297, 420), ("A2", 1199, 420, 594)]

COLLECTIONS = [
    (
        "Pretentious Fanboy",
        "collection-pretentious-fanboy.png",
        "For people who say “actually” before every sentence.",
        "You know the lap times, the tyre strategy and who should have won in 2021. Nobody asked. "
        "The wall will listen anyway.",
    ),
    (
        "Nerd Fiction",
        "collection-nerd-fiction.png",
        "Lore-heavy. Opinion-heavy. Slightly defensive.",
        "A fictional world has lived rent-free in your head for years. Time it paid something. "
        "Hang the proof.",
    ),
    (
        "Baddie Era",
        "collection-baddie-era.png",
        "Main character energy, framed.",
        "Soft launch, hard stare. These are for walls that have never once apologised.",
    ),
]

# Listed newest-first in the shop, so they're created last-to-first below.
PRODUCTS = [
    {
        "slug": "red-bull-1",
        "title": "Red Bull #1",
        "collection": "pretentious-fanboy",
        "image": "poster-red-bull-1.png",
        "room": "collection-pretentious-fanboy.png",
        "editions": 250,
        "tag": "Bestseller",
        "blurb": "Lights out and away you go, straight onto your wall.",
        "story": "A pit-lane-fast poster for the friend who calls tyre degradation “a vibe”. "
        "Loud colour, 300 GSM gloss, zero podium humility.",
        "hang_if": "you have ever paused a race to explain DRS.",
    },
    {
        "slug": "baddie-profile-1",
        "title": "Baddie Profile #1",
        "collection": "baddie-era",
        "image": "poster-baddie-profile-1.png",
        "room": "collection-baddie-era.png",
        "editions": 250,
        "tag": "Bestseller",
        "blurb": "Lotus-pink, unbothered, and not here to explain herself.",
        "story": "Collage-loud and unapologetic. It looks great in daylight and even better when "
        "someone asks who she is.",
        "hang_if": "your last profile photo started a debate.",
    },
    {
        "slug": "demon-slayer-1",
        "title": "Demon Slayer #1",
        "collection": "nerd-fiction",
        "image": "poster-demon-slayer-1.png",
        "room": "collection-nerd-fiction.png",
        "editions": 250,
        "tag": "Bestseller",
        "blurb": "The first light, in vintage ink and sun-red.",
        "story": "A field-notes style print for people who have a favourite breathing technique and "
        "are ready to discuss it.",
        "hang_if": "you have a ranking of every Hashira and it is non-negotiable.",
    },
    {
        "slug": "soul-punk",
        "title": "Soul Punk",
        "collection": "nerd-fiction",
        "image": "poster-soul-punk.png",
        "room": None,
        "editions": 150,
        "tag": "New drop",
        "blurb": "Blue skin. Gold hoops. Zero chill.",
        "story": "A riot of risograph red and a mohawk that has never heard the word “tone it down”. "
        "It will make your living room louder.",
        "hang_if": "your playlist has more screaming than lyrics.",
    },
    {
        "slug": "badmash-pani-puri-wala",
        "title": "Badmash Pani Puri Wala",
        "collection": "baddie-era",
        "image": "poster-pani-puri-wala.png",
        "room": None,
        "editions": 150,
        "tag": "Croc’s pick",
        "blurb": "Street-food royalty, now in poster form.",
        "story": "The croc has spoken. He serves the spiciest pani and the sassiest side-eye on the "
        "lane. Extra imli, no apologies.",
        "hang_if": "you judge a city by its golgappa.",
    },
]


def variants(slug: str, editions: int) -> list[VariantIn]:
    code = "".join(w[0] for w in slug.split("-")).upper()
    return [
        VariantIn(
            sku=f"HSC-{code}-{size}",
            price_paise=rupees * 100,
            weight_grams=250,
            width_mm=width,
            length_mm=height,
            position=i,
            attributes={"size": size},
            initial_stock=editions,
            low_stock_threshold=10,
        )
        for i, (size, rupees, width, height) in enumerate(SIZES)
    ]


async def main(archive_demo: bool) -> None:
    settings = get_settings()
    if settings.is_production:
        sys.exit(
            "Refusing to seed into production: confirm the placeholder prices and load them in the admin"
        )
    try:
        storage = get_media_storage()
    except MediaStorageUnavailable:
        print("Cloudinary is not configured: loading everything except the pictures.")
        storage = None

    async with SessionLocal() as db:
        if await db.scalar(select(Attribute.id).where(Attribute.code == "size")) is None:
            await taxonomy.create_attribute(
                db, AttributeIn(code="size", name="Size", sort_order=0, values=[s[0] for s in SIZES])
            )

        for order, (name, image, tagline, story) in enumerate(COLLECTIONS):
            slug = taxonomy.slugify(name)
            if await db.scalar(select(Collection.id).where(Collection.slug == slug)) is None:
                stored = None
                if storage:
                    data = (ASSETS / image).read_bytes()
                    stored = await storage.upload(data, f"{settings.media_folder}/collections")
                await taxonomy.create_collection(
                    db,
                    CollectionIn(
                        name=name,
                        slug=slug,
                        description=f"{tagline}\n\n{story}",
                        image_url=stored.url if stored else None,
                        sort_order=order,
                    ),
                )
                print(f"Created collection {name}")

        collections = dict((await db.execute(select(Collection.slug, Collection.id))).all())
        for p in reversed(PRODUCTS):
            product_id = await db.scalar(select(Product.id).where(Product.slug == p["slug"]))
            if product_id is None:
                created = await service.create_product(
                    db,
                    ProductIn(
                        title=p["title"],
                        slug=p["slug"],
                        status="ACTIVE",
                        short_description=p["blurb"],
                        description=f"{p['story']}\n\nHang it if {p['hang_if']}",
                        collection_ids=[collections[p["collection"]]],
                        tags=[p["tag"], f"{p['editions']} editions"],
                        variants=variants(p["slug"], p["editions"]),
                    ),
                    None,
                )
                product_id = created.id
                print(f"Created {p['title']}")
            shots = [(p["image"], f"{p['title']} poster")]
            if p["room"]:
                shots.append((p["room"], f"{p['title']} poster in a room"))
            have = await db.scalar(select(func.count()).where(ProductMedia.product_id == product_id))
            for file, alt in shots[have:] if storage else []:
                await service.add_media(
                    db, storage, settings.media_folder, product_id, (ASSETS / file).read_bytes(), alt, None
                )
                print(f"Uploaded {file}")

        if await db.scalar(select(Coupon.id).where(Coupon.code == "WELCOME10")) is None:
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

        if archive_demo:
            demo_slugs = [taxonomy.slugify(row[0]) for row in DEMO_PRODUCTS]
            demo_cols = [taxonomy.slugify(name) for name in DEMO_COLLECTIONS]
            hidden = await db.execute(
                update(Product).where(Product.slug.in_(demo_slugs)).values(status=ProductStatus.ARCHIVED)
            )
            await db.execute(update(Collection).where(Collection.slug.in_(demo_cols)).values(is_active=False))
            await db.commit()
            await invalidate(taxonomy.COLLECTIONS_KEY)
            print(f"Archived {hidden.rowcount} demo products")  # type: ignore[attr-defined]
    print("Done. Open /shop")


if __name__ == "__main__":
    asyncio.run(main("--archive-demo" in sys.argv))
