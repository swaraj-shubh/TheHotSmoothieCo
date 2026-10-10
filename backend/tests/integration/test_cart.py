import uuid


async def test_guest_cart_flow_and_token(client, shop):
    r = await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["NT-A4"], "quantity": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    token = body["cart_token"]
    assert token and body["item_count"] == 1
    assert body["totals"] == {
        "subtotal_paise": 40000,
        "discount_paise": 0,
        "shipping_paise": 9900,
        "tax_paise": 6102,
        "total_paise": 49900,
        "prices_include_tax": True,
    }

    h = {"X-Cart-Token": token}
    r = await client.post(
        "/api/v1/cart/items", json={"variant_id": shop["skus"]["NT-A4"], "quantity": 1}, headers=h
    )
    assert (
        r.json()["items"][0]["quantity"] == 2 and r.json()["cart_token"] is None
    )  # same cart, quantities add

    # Without the token it's a different (empty) cart.
    assert (await client.get("/api/v1/cart")).json()["items"] == []
    assert (await client.get("/api/v1/cart", headers={"X-Cart-Token": "forged-token-forged-token"})).json()[
        "items"
    ] == []


async def test_stock_and_quantity_rules(client, shop, customer):
    vid = shop["skus"]["NT-A4"]  # 2 in stock
    r = await client.post("/api/v1/cart/items", json={"variant_id": vid, "quantity": 3}, headers=customer)
    assert r.status_code == 409 and r.json()["error"]["code"] == "INSUFFICIENT_INVENTORY"
    assert (await client.get("/api/v1/cart", headers=customer)).json()["items"] == []  # nothing half-saved

    item = (
        await client.post("/api/v1/cart/items", json={"variant_id": vid, "quantity": 2}, headers=customer)
    ).json()["items"][0]
    r = await client.patch(f"/api/v1/cart/items/{item['id']}", json={"quantity": 5}, headers=customer)
    assert r.status_code == 409
    r = await client.patch(f"/api/v1/cart/items/{item['id']}", json={"quantity": 1}, headers=customer)
    assert r.json()["items"][0]["quantity"] == 1

    r = await client.post("/api/v1/cart/items", json={"variant_id": str(uuid.uuid4())}, headers=customer)
    assert r.json()["error"]["code"] == "VARIANT_UNAVAILABLE"


async def test_cart_reflects_live_price_and_availability(client, shop, customer):
    vid = shop["skus"]["NT-A3"]
    await client.post("/api/v1/cart/items", json={"variant_id": vid, "quantity": 2}, headers=customer)

    a = shop["products"]["a"]
    await client.patch(
        f"/api/v1/admin/products/{a['id']}/variants/{vid}", json={"price_paise": 99900}, headers=shop["pm"]
    )
    cart = (await client.get("/api/v1/cart", headers=customer)).json()
    assert cart["items"][0]["unit_price_paise"] == 99900 and cart["totals"]["subtotal_paise"] == 199800

    await client.patch(f"/api/v1/admin/products/{a['id']}", json={"status": "ARCHIVED"}, headers=shop["pm"])
    cart = (await client.get("/api/v1/cart", headers=customer)).json()
    assert cart["items"][0]["issue"] == "UNAVAILABLE"
    assert cart["checkout_ready"] is False and cart["totals"]["subtotal_paise"] == 0


async def test_merge_guest_cart_on_login(client, shop, customer):
    guest = (
        await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["SP-1"], "quantity": 3})
    ).json()
    await client.post(
        "/api/v1/cart/items", json={"variant_id": shop["skus"]["SP-1"], "quantity": 2}, headers=customer
    )
    await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["NT-A4"]}, headers=customer)

    merged = (
        await client.post("/api/v1/cart/merge", headers={**customer, "X-Cart-Token": guest["cart_token"]})
    ).json()
    assert {i["sku"]: i["quantity"] for i in merged["items"]} == {"SP-1": 5, "NT-A4": 1}
    # Guest cart is gone; merging again is harmless.
    assert (await client.get("/api/v1/cart", headers={"X-Cart-Token": guest["cart_token"]})).json()[
        "items"
    ] == []
    again = (
        await client.post("/api/v1/cart/merge", headers={**customer, "X-Cart-Token": guest["cart_token"]})
    ).json()
    assert again["item_count"] == 6


async def test_cart_item_ownership(client, shop, customer, make_user):
    item = (
        await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["SP-1"]}, headers=customer)
    ).json()["items"][0]
    _, other = await make_user("other@example.com")
    await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["SP-1"]}, headers=other)
    r = await client.delete(f"/api/v1/cart/items/{item['id']}", headers=other)
    assert r.status_code == 404


async def test_coupon_apply_and_errors(client, shop, customer, staff):
    mk = await staff("MARKETING_MANAGER")
    r = await client.post(
        "/api/v1/admin/coupons",
        json={"code": "welcome10", "discount_type": "PERCENT", "value": 10, "min_subtotal_paise": 50000},
        headers=mk,
    )
    assert r.status_code == 201 and r.json()["code"] == "WELCOME10"
    await client.post(
        "/api/v1/admin/coupons",
        json={"code": "OLD", "discount_type": "FIXED", "value": 100, "ends_at": "2020-01-01T00:00:00Z"},
        headers=mk,
    )

    r = await client.post("/api/v1/cart/coupon", json={"code": "WELCOME10"}, headers=customer)
    assert r.json()["error"]["message"] == "Add something to your cart first"
    await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["NT-A4"]}, headers=customer)

    r = await client.post("/api/v1/cart/coupon", json={"code": "welcome10"}, headers=customer)
    assert (
        r.json()["error"]["code"] == "INVALID_COUPON" and "more" in r.json()["error"]["message"]
    )  # ₹400 < ₹500
    assert (await client.post("/api/v1/cart/coupon", json={"code": "OLD"}, headers=customer)).json()["error"][
        "message"
    ] == "This coupon has expired"
    assert (
        await client.post("/api/v1/cart/coupon", json={"code": "NOPE1"}, headers=customer)
    ).status_code == 400

    await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["NT-A3"]}, headers=customer)
    cart = (await client.post("/api/v1/cart/coupon", json={"code": "welcome10"}, headers=customer)).json()
    assert cart["coupon_code"] == "WELCOME10"
    assert cart["totals"]["discount_paise"] == 16000 and cart["totals"]["total_paise"] == 144000

    # Coupon stays but reports why it no longer applies when the cart drops below the minimum.
    a3 = next(i for i in cart["items"] if i["sku"] == "NT-A3")
    cart = (await client.delete(f"/api/v1/cart/items/{a3['id']}", headers=customer)).json()
    assert cart["coupon_error"] and cart["totals"]["discount_paise"] == 0 and cart["checkout_ready"] is False

    cart = (await client.delete("/api/v1/cart/coupon", headers=customer)).json()
    assert cart["coupon_code"] is None and cart["checkout_ready"] is True
