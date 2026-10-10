from tests.integration.test_payments import paid_order

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


async def review(client, headers, product_id, rating=5, **kw):
    return await client.post(
        "/api/v1/reviews", json={"product_id": product_id, "rating": rating, **kw}, headers=headers
    )


async def test_moderation_rating_and_verified_badge(client, shop, customer, pay, make_user, staff):
    mod = await staff("CUSTOMER_SUPPORT")
    product = shop["products"]["b"]
    await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    _, browser = await make_user("browser@example.com")

    mine = (await review(client, customer, product["id"], 5, title="Love it", body="Vivid colours")).json()
    theirs = (await review(client, browser, product["id"], 2, body="Meh")).json()
    assert mine["status"] == "PENDING" and mine["verified_purchase"] is True
    assert theirs["verified_purchase"] is False

    slug = product["slug"]
    assert (await client.get(f"/api/v1/products/{slug}/reviews")).json()[
        "items"
    ] == []  # nothing until approved
    for rid in (mine["id"], theirs["id"]):
        assert (
            await client.post(f"/api/v1/admin/reviews/{rid}/approve", json={}, headers=mod)
        ).status_code == 200

    public = (await client.get(f"/api/v1/products/{slug}/reviews")).json()["items"]
    assert {r["author"] for r in public} == {"T", "browser"}  # display name only, never email
    summary = (await client.get(f"/api/v1/products/{slug}/reviews/summary")).json()
    assert summary == {"count": 2, "average": 3.5, "distribution": {"5": 1, "4": 0, "3": 0, "2": 1, "1": 0}}
    detail = (await client.get(f"/api/v1/products/{slug}")).json()
    card = next(c for c in (await client.get("/api/v1/products")).json()["items"] if c["slug"] == slug)
    assert (
        (detail["rating_average"], detail["rating_count"])
        == (3.5, 2)
        == (card["rating_average"], card["rating_count"])
    )

    only5 = (await client.get(f"/api/v1/products/{slug}/reviews", params={"rating": 5})).json()["items"]
    assert [r["rating"] for r in only5] == [5]

    # Editing sends it back to moderation and out of the average.
    edited = (
        await client.patch(f"/api/v1/reviews/{theirs['id']}", json={"rating": 1}, headers=browser)
    ).json()
    assert edited["status"] == "PENDING"
    assert (await client.get(f"/api/v1/products/{slug}")).json()["rating_count"] == 1

    await client.post(f"/api/v1/admin/reviews/{theirs['id']}/reject", json={"note": "Off-topic"}, headers=mod)
    mine_list = (await client.get("/api/v1/reviews/mine", headers=browser)).json()
    assert mine_list[0]["status"] == "REJECTED" and mine_list[0]["moderation_note"] == "Off-topic"


async def test_one_review_per_product_and_delete_frees_slot(client, shop, customer):
    pid = shop["products"]["a"]["id"]
    first = (await review(client, customer, pid)).json()
    dup = await review(client, customer, pid)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "REVIEW_EXISTS"
    assert (await client.delete(f"/api/v1/reviews/{first['id']}", headers=customer)).status_code == 204
    assert (await review(client, customer, pid, 4)).status_code == 201


async def test_validation_ownership_and_rbac(client, shop, customer, make_user):
    pid = shop["products"]["a"]["id"]
    assert (await review(client, customer, pid, 6)).status_code == 422
    assert (await review(client, customer, pid, 5, body="bad\x00byte")).status_code == 422
    r = (await review(client, customer, pid)).json()
    _, other = await make_user("other@example.com")
    assert (
        await client.patch(f"/api/v1/reviews/{r['id']}", json={"rating": 1}, headers=other)
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/admin/reviews/{r['id']}/approve", json={}, headers=other)
    ).status_code == 403
    assert (await client.post("/api/v1/reviews", json={"product_id": pid, "rating": 5})).status_code == 401


async def test_review_photos(client, shop, customer, staff, storage):
    mod = await staff("ADMIN")
    r = (await review(client, customer, shop["products"]["a"]["id"])).json()
    await client.post(f"/api/v1/admin/reviews/{r['id']}/approve", json={}, headers=mod)
    url = f"/api/v1/reviews/{r['id']}/media"
    bad = await client.post(url, files={"file": ("x.png", b"GIF89a....", "image/png")}, headers=customer)
    assert bad.json()["error"]["code"] == "INVALID_UPLOAD"
    with_photo = (
        await client.post(url, files={"file": ("x.png", PNG, "image/png")}, headers=customer)
    ).json()
    assert len(with_photo["media"]) == 1 and with_photo["status"] == "PENDING"  # photos are moderated too
    queue = (await client.get("/api/v1/admin/reviews", headers=mod)).json()["items"]
    assert [q["id"] for q in queue] == [r["id"]]
    assert queue[0]["product_title"] and "@" in queue[0]["author_email"]


def test_display_name_hides_surname():
    from app.reviews.service import display_name

    assert display_name("Ada Lovelace") == "Ada L."
    assert display_name("Ada King Lovelace") == "Ada L."
    assert display_name("Cher") == "Cher"
    assert display_name("  ") == "Customer"
