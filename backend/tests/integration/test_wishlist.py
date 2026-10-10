async def test_wishlist_add_is_idempotent_and_lists_cards(client, shop, customer):
    pid = shop["products"]["a"]["id"]
    r1 = await client.post("/api/v1/wishlist", json={"product_id": pid}, headers=customer)
    r2 = await client.post("/api/v1/wishlist", json={"product_id": pid}, headers=customer)
    assert r1.status_code == r2.status_code == 201 and r1.json()["id"] == r2.json()["id"]
    await client.post(
        "/api/v1/wishlist", json={"product_id": pid, "variant_id": shop["skus"]["NT-A4"]}, headers=customer
    )
    items = (await client.get("/api/v1/wishlist", headers=customer)).json()["items"]
    assert len(items) == 2
    assert items[0]["variant"]["title"] == "None / A4" and items[0]["product"]["title"] == "Neon Tokyo"

    r = await client.post(
        "/api/v1/wishlist", json={"product_id": pid, "variant_id": shop["skus"]["SP-1"]}, headers=customer
    )
    assert r.json()["error"]["code"] == "VARIANT_MISMATCH"


async def test_move_to_cart(client, shop, customer):
    multi = (
        await client.post(
            "/api/v1/wishlist", json={"product_id": shop["products"]["a"]["id"]}, headers=customer
        )
    ).json()
    single = (
        await client.post(
            "/api/v1/wishlist", json={"product_id": shop["products"]["b"]["id"]}, headers=customer
        )
    ).json()

    r = await client.post(f"/api/v1/wishlist/{multi['id']}/move-to-cart", json={}, headers=customer)
    assert r.json()["error"]["code"] == "VARIANT_REQUIRED"  # two sizes: customer must pick

    cart = (
        await client.post(
            f"/api/v1/wishlist/{single['id']}/move-to-cart", json={"quantity": 2}, headers=customer
        )
    ).json()
    assert cart["items"][0]["sku"] == "SP-1" and cart["items"][0]["quantity"] == 2

    r = await client.post(
        f"/api/v1/wishlist/{multi['id']}/move-to-cart",
        json={"variant_id": shop["skus"]["NT-A4"], "quantity": 5},
        headers=customer,
    )
    assert r.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"
    remaining = (await client.get("/api/v1/wishlist", headers=customer)).json()["items"]
    assert [i["id"] for i in remaining] == [multi["id"]]  # failed move left it in the wishlist


async def test_wishlist_privacy_and_auth(client, shop, customer, make_user):
    item = (
        await client.post(
            "/api/v1/wishlist", json={"product_id": shop["products"]["b"]["id"]}, headers=customer
        )
    ).json()
    _, other = await make_user("other@example.com")
    assert (await client.delete(f"/api/v1/wishlist/{item['id']}", headers=other)).status_code == 404
    assert (await client.get("/api/v1/wishlist")).status_code == 401
