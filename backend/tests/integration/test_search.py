import pytest

from app.core.database import SessionLocal
from app.search.backend import reindex_all
from tests.integration.test_catalog import create_product, setup_taxonomy, variant


@pytest.fixture
async def catalog(client, staff):
    pm = await staff("PRODUCT_MANAGER")
    posters, movies, retro = await setup_taxonomy(client, pm)
    await create_product(
        client,
        pm,
        "Neon Tokyo Nights",
        [variant("NEON-A3", "A3", "Black", 150000)],
        category_id=posters["id"],
        tags=["cyberpunk"],
        short_description="Rainy streets in pink light",
    )
    await create_product(
        client,
        pm,
        "Pulp Fiction Minimal",
        [variant("PULP-A4", "A4", "None", 50000)],
        category_id=movies["id"],
        collection_ids=[retro["id"]],
        description="A classic film poster. Neon diner sign.",
    )
    draft = {"title": "Neon Draft", "variants": [variant("DRAFT-1", "A4", "None", 1)]}
    await client.post("/api/v1/admin/products", json=draft, headers=pm)  # DRAFT: never searchable
    return {"pm": pm, "posters": posters}


async def titles(client, **params):
    r = await client.get("/api/v1/search", params=params)
    assert r.status_code == 200, r.text
    return [i["title"] for i in r.json()["items"]], r.json()


async def test_keyword_prefix_ranking_and_fields(client, catalog):
    found, _ = await titles(client, q="neon")
    assert found == ["Neon Tokyo Nights", "Pulp Fiction Minimal"]  # title beats description
    assert (await titles(client, q="neo"))[0][0] == "Neon Tokyo Nights"  # prefix / search-as-you-type
    assert (await titles(client, q="cyberpunk"))[0] == ["Neon Tokyo Nights"]  # tag
    assert (await titles(client, q="movie"))[0] == ["Pulp Fiction Minimal"]  # category name (stemmed)
    assert (await titles(client, q="retro summer"))[0] == ["Pulp Fiction Minimal"]  # collection
    assert (await titles(client, q="pulp-a4"))[0] == ["Pulp Fiction Minimal"]  # exact SKU
    assert (await titles(client, q="black"))[0] == ["Neon Tokyo Nights"]  # option value (frame)


async def test_filters_sorting_and_pagination_compose(client, catalog):
    found, _ = await titles(client, q="neon", sort="price_asc")
    assert found == ["Pulp Fiction Minimal", "Neon Tokyo Nights"]
    found, _ = await titles(client, q="neon", attr="size:a3")
    assert found == ["Neon Tokyo Nights"]
    found, _ = await titles(client, q="neon", max_price=60000)
    assert found == ["Pulp Fiction Minimal"]

    page1 = (await client.get("/api/v1/search", params={"q": "neon", "limit": 1})).json()
    page2 = (
        await client.get("/api/v1/search", params={"q": "neon", "limit": 1, "cursor": page1["next_cursor"]})
    ).json()
    assert [page1["items"][0]["title"], page2["items"][0]["title"]] == [
        "Neon Tokyo Nights",
        "Pulp Fiction Minimal",
    ]
    assert page2["next_cursor"] is None


async def test_typo_tolerance_and_junk_input(client, catalog):
    found, body = await titles(client, q="tokio nights")
    assert found == ["Neon Tokyo Nights"] and body["fuzzy"] is True
    found, body = await titles(client, q="!!! ***")  # nothing searchable, no SQL error
    assert found == [] and body["fuzzy"] is False
    found, _ = await titles(client, q="') OR 1=1 --")
    assert found == []
    assert (await client.get("/api/v1/search", params={"q": ""})).status_code == 422


async def test_suggest(client, catalog):
    r = (await client.get("/api/v1/search/suggest", params={"q": "pul"})).json()
    assert r == [{"slug": "pulp-fiction-minimal", "title": "Pulp Fiction Minimal"}]


async def test_index_follows_product_edits_and_category_renames(client, catalog):
    pm = catalog["pm"]
    pid = (await client.get("/api/v1/search", params={"q": "neon tokyo"})).json()["items"][0]["id"]
    await client.patch(f"/api/v1/admin/products/{pid}", json={"tags": ["synthwave"]}, headers=pm)
    assert (await titles(client, q="synthwave"))[0] == [
        "Neon Tokyo Nights"
    ]  # indexed in the same transaction
    assert (await titles(client, q="cyberpunk"))[0] == []

    await client.patch(
        f"/api/v1/admin/categories/{catalog['posters']['id']}", json={"name": "Wall Art"}, headers=pm
    )
    async with SessionLocal() as db:
        assert await reindex_all(db) >= 1  # the periodic job picks up taxonomy renames
    assert (await titles(client, q="wall art"))[0] == ["Neon Tokyo Nights"]
