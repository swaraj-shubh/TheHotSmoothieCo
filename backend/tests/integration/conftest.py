import pytest

from tests.integration.test_catalog import create_product, setup_taxonomy, variant


@pytest.fixture
async def shop(client, staff):
    """Two products; returns {sku: variant_id} plus the PM headers."""
    pm = await staff("PRODUCT_MANAGER")
    await setup_taxonomy(client, pm)
    a = await create_product(
        client,
        pm,
        "Neon Tokyo",
        [variant("NT-A3", "A3", "Black", 120000, stock=5), variant("NT-A4", "A4", "None", 40000, stock=2)],
    )
    b = await create_product(client, pm, "Sticker Pack", [variant("SP-1", "A4", "None", 15000, stock=100)])
    skus = {v["sku"]: v["id"] for p in (a, b) for v in p["variants"]}
    return {"skus": skus, "pm": pm, "products": {"a": a, "b": b}}
