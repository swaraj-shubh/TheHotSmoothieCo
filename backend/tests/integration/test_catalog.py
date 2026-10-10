import pytest

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
async def pm(staff):
    return await staff("PRODUCT_MANAGER")


async def setup_taxonomy(client, h):
    for code, name, values in [
        ("size", "Size", ["A4", "A3", "A2"]),
        ("frame", "Frame", ["None", "Black", "White"]),
    ]:
        r = await client.post(
            "/api/v1/admin/attributes", json={"code": code, "name": name, "values": values}, headers=h
        )
        assert r.status_code == 201, r.text
    posters = (await client.post("/api/v1/admin/categories", json={"name": "Posters"}, headers=h)).json()
    movies = (
        await client.post(
            "/api/v1/admin/categories", json={"name": "Movie Posters", "parent_id": posters["id"]}, headers=h
        )
    ).json()
    retro = (await client.post("/api/v1/admin/collections", json={"name": "Retro Summer"}, headers=h)).json()
    return posters, movies, retro


def variant(sku, size, frame, price, stock=10, **kw):
    return {
        "sku": sku,
        "price_paise": price,
        "attributes": {"size": size, "frame": frame},
        "initial_stock": stock,
        **kw,
    }


async def create_product(client, h, title, variants, **kw):
    r = await client.post(
        "/api/v1/admin/products",
        json={"title": title, "status": "ACTIVE", "variants": variants, **kw},
        headers=h,
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_product_with_variants_and_public_detail(client, pm):
    _, movies, retro = await setup_taxonomy(client, pm)
    p = await create_product(
        client,
        pm,
        "Pulp Fiction — Minimal Print",
        [
            variant("PF-A3-BLK", "A3", "Black", 149900, compare_at_price_paise=199900),
            variant("PF-A4-NONE", "A4", "None", 49900),
            variant("PF-A3-WHT", "A3", "White", 149900, stock=0),
        ],
        category_id=movies["id"],
        collection_ids=[retro["id"]],
        tags=["Movies", "Minimal", "movies"],
        short_description="Bold and minimal.",
    )
    assert p["slug"] == "pulp-fiction-minimal-print"
    assert (p["min_price_paise"], p["max_price_paise"]) == (49900, 149900)
    assert {v["sku"]: v["on_hand"] for v in p["variants"]} == {
        "PF-A3-BLK": 10,
        "PF-A4-NONE": 10,
        "PF-A3-WHT": 0,
    }
    assert sorted(t["slug"] for t in p["tags"]) == ["minimal", "movies"]

    pub = (await client.get(f"/api/v1/products/{p['slug']}")).json()
    assert pub["category"]["slug"] == "movie-posters"
    # Selector options follow the attribute's own value order, not insertion order.
    assert pub["options"] == [
        {"code": "frame", "name": "Frame", "values": ["None", "Black", "White"]},
        {"code": "size", "name": "Size", "values": ["A4", "A3"]},
    ]
    by_sku = {v["sku"]: v for v in pub["variants"]}
    assert by_sku["PF-A3-BLK"]["attributes"] == {"size": "A3", "frame": "Black"}
    assert by_sku["PF-A3-BLK"]["title"] == "Black / A3"
    assert by_sku["PF-A3-WHT"]["in_stock"] is False
    assert by_sku["PF-A4-NONE"]["max_purchasable"] == 10
    assert "on_hand" not in by_sku["PF-A4-NONE"]  # exact stock is admin-only


async def test_variant_rules(client, pm):
    await setup_taxonomy(client, pm)
    bad = [
        ([variant("X1", "A3", "Black", 100), variant("X2", "A3", "Black", 100)], "INVALID_VARIANTS"),
        (
            [
                variant("X1", "A3", "Black", 100),
                {"sku": "X2", "price_paise": 1, "attributes": {"size": "A4"}},
            ],
            "INVALID_VARIANTS",
        ),
        (
            [variant("X1", "A3", "Black", 100), variant("x1", "A4", "Black", 100)],
            "SKU_TAKEN",
        ),  # SKUs upper-cased
        ([{"sku": "X1", "price_paise": 100, "attributes": {"colour": "red"}}], "UNKNOWN_ATTRIBUTE"),
    ]
    for variants, code in bad:
        r = await client.post("/api/v1/admin/products", json={"title": "T", "variants": variants}, headers=pm)
        assert r.status_code in (400, 409), r.text
        assert r.json()["error"]["code"] == code

    r = await client.post(
        "/api/v1/admin/products",
        json={"title": "T", "variants": [variant("X1", "A3", "Black", 100, compare_at_price_paise=50)]},
        headers=pm,
    )
    assert r.status_code == 422  # compare-at must exceed price


async def test_sku_unique_across_products(client, pm):
    await setup_taxonomy(client, pm)
    await create_product(client, pm, "One", [variant("SAME", "A3", "Black", 100)])
    r = await client.post(
        "/api/v1/admin/products",
        json={"title": "Two", "variants": [variant("SAME", "A4", "None", 100)]},
        headers=pm,
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "SKU_TAKEN"


async def test_drafts_and_archived_are_hidden(client, pm):
    await setup_taxonomy(client, pm)
    p = await create_product(client, pm, "Secret", [variant("S1", "A3", "Black", 100)])
    await client.patch(f"/api/v1/admin/products/{p['id']}", json={"status": "ARCHIVED"}, headers=pm)
    assert (await client.get("/api/v1/products/secret")).status_code == 404
    assert (await client.get("/api/v1/products")).json()["items"] == []


async def test_listing_filters_sorting_and_cursor_pagination(client, pm):
    posters, movies, retro = await setup_taxonomy(client, pm)
    await create_product(
        client, pm, "Cheap A4", [variant("C1", "A4", "None", 30000)], category_id=posters["id"]
    )
    await create_product(
        client,
        pm,
        "Movie A3 Black",
        [variant("M1", "A3", "Black", 150000)],
        category_id=movies["id"],
        collection_ids=[retro["id"]],
        tags=["noir"],
    )
    await create_product(
        client, pm, "Sold Out", [variant("SO1", "A3", "White", 90000, stock=0)], category_id=movies["id"]
    )

    async def titles(**params):
        r = await client.get("/api/v1/products", params=params)
        assert r.status_code == 200, r.text
        return [i["title"] for i in r.json()["items"]]

    assert await titles() == ["Sold Out", "Movie A3 Black", "Cheap A4"]  # newest first
    assert await titles(sort="price_asc") == ["Cheap A4", "Sold Out", "Movie A3 Black"]
    assert set(await titles(category="posters")) == {
        "Cheap A4",
        "Movie A3 Black",
        "Sold Out",
    }  # includes children
    assert set(await titles(category="movie-posters")) == {"Movie A3 Black", "Sold Out"}
    assert await titles(collection="retro-summer") == ["Movie A3 Black"]
    assert await titles(tag="noir") == ["Movie A3 Black"]
    assert set(await titles(in_stock="true")) == {"Cheap A4", "Movie A3 Black"}
    assert set(await titles(attr="size:a3")) == {"Movie A3 Black", "Sold Out"}
    assert await titles(attr=["size:a3", "frame:black"]) == ["Movie A3 Black"]
    assert await titles(min_price=50000, max_price=100000) == ["Sold Out"]

    # Cursor pagination walks every item exactly once.
    seen, cursor = [], None
    while True:
        params = {"limit": 1, "sort": "price_desc", **({"cursor": cursor} if cursor else {})}
        body = (await client.get("/api/v1/products", params=params)).json()
        seen += [i["title"] for i in body["items"]]
        if not (cursor := body["next_cursor"]):
            break
    assert seen == ["Movie A3 Black", "Sold Out", "Cheap A4"]

    card = (await client.get("/api/v1/products", params={"tag": "noir"})).json()["items"][0]
    assert card["in_stock"] is True and card["image_url"] is None

    assert (await client.get("/api/v1/products", params={"cursor": "garbage"})).json()["error"][
        "code"
    ] == "INVALID_CURSOR"
    assert (await client.get("/api/v1/products", params={"category": "nope"})).status_code == 404


async def test_category_tree_cached_and_invalidated(client, pm):
    posters, _, _ = await setup_taxonomy(client, pm)
    tree = (await client.get("/api/v1/categories")).json()
    assert tree[0]["slug"] == "posters" and tree[0]["children"][0]["slug"] == "movie-posters"

    await client.patch(f"/api/v1/admin/categories/{posters['id']}", json={"name": "Wall Posters"}, headers=pm)
    assert (await client.get("/api/v1/categories")).json()[0]["name"] == "Wall Posters"

    await client.patch(f"/api/v1/admin/categories/{posters['id']}", json={"is_active": False}, headers=pm)
    assert (await client.get("/api/v1/categories")).json() == []  # hides the subtree too


async def test_category_rules(client, pm):
    posters, movies, _ = await setup_taxonomy(client, pm)
    r = await client.patch(
        f"/api/v1/admin/categories/{posters['id']}", json={"parent_id": movies["id"]}, headers=pm
    )
    assert r.json()["error"]["code"] == "CATEGORY_CYCLE"
    r = await client.post("/api/v1/admin/categories", json={"name": "Posters"}, headers=pm)
    assert r.status_code == 409 and r.json()["error"]["code"] == "SLUG_TAKEN"
    r = await client.delete(f"/api/v1/admin/categories/{posters['id']}", headers=pm)
    assert r.status_code == 409 and r.json()["error"]["code"] == "IN_USE"  # has a child


async def test_variant_updates_keep_price_range_and_rules(client, pm):
    await setup_taxonomy(client, pm)
    p = await create_product(
        client, pm, "Range", [variant("R1", "A4", "None", 10000), variant("R2", "A3", "None", 20000)]
    )
    v1, v2 = p["variants"]

    p = (
        await client.patch(
            f"/api/v1/admin/products/{p['id']}/variants/{v2['id']}", json={"price_paise": 5000}, headers=pm
        )
    ).json()
    assert (p["min_price_paise"], p["max_price_paise"]) == (5000, 10000)

    p = (
        await client.patch(
            f"/api/v1/admin/products/{p['id']}/variants/{v2['id']}", json={"is_active": False}, headers=pm
        )
    ).json()
    assert (p["min_price_paise"], p["max_price_paise"]) == (10000, 10000)
    r = await client.patch(
        f"/api/v1/admin/products/{p['id']}/variants/{v1['id']}", json={"is_active": False}, headers=pm
    )
    assert r.json()["error"]["code"] == "INVALID_VARIANTS"  # last active variant of a live product

    r = await client.post(
        f"/api/v1/admin/products/{p['id']}/variants",
        json=variant("R3", "A2", "None", 30000, stock=4),
        headers=pm,
    )
    assert r.status_code == 201 and r.json()["max_price_paise"] == 30000
    r = await client.post(
        f"/api/v1/admin/products/{p['id']}/variants", json=variant("R4", "A4", "None", 1), headers=pm
    )
    assert r.json()["error"]["code"] == "INVALID_VARIANTS"  # duplicates active R1


async def test_rbac_on_admin_catalog(client, customer, staff):
    assert (
        await client.post("/api/v1/admin/categories", json={"name": "X"}, headers=customer)
    ).status_code == 403
    inv = await staff("INVENTORY_MANAGER")
    assert (await client.post("/api/v1/admin/categories", json={"name": "X"}, headers=inv)).status_code == 403
    assert (await client.post("/api/v1/admin/categories", json={"name": "X"})).status_code == 401


async def test_media_upload_validation_and_lifecycle(client, pm, storage):
    await setup_taxonomy(client, pm)
    p = await create_product(client, pm, "Pic", [variant("P1", "A3", "Black", 100)])
    url = f"/api/v1/admin/products/{p['id']}/media"

    r = await client.post(url, files={"file": ("evil.png", b"<?php echo 1; ?>", "image/png")}, headers=pm)
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_UPLOAD"  # spoofed content type

    r = await client.post(
        url, files={"file": ("a.png", PNG, "image/png")}, data={"alt_text": "Poster"}, headers=pm
    )
    assert r.status_code == 201, r.text
    media = r.json()

    card = (await client.get("/api/v1/products")).json()["items"][0]
    assert card["thumbnail_url"] == media["thumbnail_url"] and card["image_alt"] == "Poster"

    assert (await client.delete(f"{url}/{media['id']}", headers=pm)).status_code == 204
    assert storage.deleted == [next(iter(storage.files))]


async def test_media_upload_without_storage_configured(client, pm):
    await setup_taxonomy(client, pm)
    p = await create_product(client, pm, "Pic", [variant("P1", "A3", "Black", 100)])
    r = await client.post(
        f"/api/v1/admin/products/{p['id']}/media", files={"file": ("a.png", PNG, "image/png")}, headers=pm
    )
    assert r.status_code == 503 and r.json()["error"]["code"] == "MEDIA_STORAGE_UNAVAILABLE"


async def test_admin_product_search(client, pm):
    await setup_taxonomy(client, pm)
    await create_product(client, pm, "Alpha", [variant("ALPHA-1", "A3", "Black", 100)])
    await create_product(client, pm, "Beta", [variant("BETA-1", "A3", "Black", 100)])
    r = await client.get("/api/v1/admin/products", params={"q": "beta-1"}, headers=pm)
    assert [i["title"] for i in r.json()["items"]] == ["Beta"]
