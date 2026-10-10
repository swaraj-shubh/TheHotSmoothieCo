import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.checkout import service as checkout
from app.checkout.service import CheckoutIn
from app.core.database import SessionLocal
from app.coupons.models import Coupon
from app.inventory.models import Inventory
from app.orders import service as orders
from app.orders.models import Order
from app.users.models import User
from tests.integration.test_addresses import ADDR


async def address(client, headers) -> str:
    return (await client.post("/api/v1/users/me/addresses", json=ADDR, headers=headers)).json()["id"]


async def add(client, headers, variant_id, qty=1):
    r = await client.post(
        "/api/v1/cart/items", json={"variant_id": variant_id, "quantity": qty}, headers=headers
    )
    assert r.status_code == 200, r.text
    return r.json()


async def place(client, headers, addr_id, key=None, **extra):
    return await client.post(
        "/api/v1/checkout",
        json={"shipping_address_id": addr_id, **extra},
        headers={**headers, "Idempotency-Key": key or uuid.uuid4().hex},
    )


async def stock(variant_id) -> Inventory:
    async with SessionLocal() as s:
        return await s.get(Inventory, uuid.UUID(variant_id))


async def test_checkout_creates_snapshotted_order_and_holds_stock(client, shop, customer):
    vid = shop["skus"]["NT-A3"]
    addr = await address(client, customer)
    cart = await add(client, customer, vid, 2)

    r = await place(client, customer, addr, expected_total_paise=cart["totals"]["total_paise"])
    assert r.status_code == 201, r.text
    order = r.json()
    assert order["status"] == "PENDING_PAYMENT" and order["number"].startswith("HSC-")
    assert order["total_paise"] == 240000 and order["shipping_paise"] == 0
    assert order["items"][0]["product_title"] == "Neon Tokyo" and order["items"][0]["attributes"] == {
        "size": "A3",
        "frame": "Black",
    }
    assert order["shipping_address"]["city"] == "Bengaluru"
    assert [h["to_status"] for h in order["history"]] == ["PENDING_PAYMENT"]
    inv = await stock(vid)
    assert (inv.on_hand, inv.reserved) == (5, 2)

    # Later catalog/address edits never rewrite the order.
    a = shop["products"]["a"]
    await client.patch(f"/api/v1/admin/products/{a['id']}", json={"title": "Renamed"}, headers=shop["pm"])
    await client.patch(
        f"/api/v1/admin/products/{a['id']}/variants/{vid}", json={"price_paise": 1}, headers=shop["pm"]
    )
    await client.put(f"/api/v1/users/me/addresses/{addr}", json={**ADDR, "city": "Chennai"}, headers=customer)
    again = (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()
    assert (
        again["items"][0]["product_title"] == "Neon Tokyo" and again["items"][0]["unit_price_paise"] == 120000
    )
    assert again["shipping_address"]["city"] == "Bengaluru"


async def test_same_idempotency_key_returns_same_order(client, shop, customer):
    addr = await address(client, customer)
    await add(client, customer, shop["skus"]["SP-1"], 3)
    first = await place(client, customer, addr, key="checkout-attempt-1")
    second = await place(client, customer, addr, key="checkout-attempt-1")
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert (await stock(shop["skus"]["SP-1"])).reserved == 3  # held once


async def test_concurrent_double_submit_creates_one_order(client, shop, customer):
    addr = await address(client, customer)
    await add(client, customer, shop["skus"]["SP-1"], 2)
    async with SessionLocal() as s:
        user = await s.scalar(select(User).where(User.email == "customer@example.com"))

    async def attempt():
        async with SessionLocal() as s:
            order, _ = await checkout.place_order(
                s, user, CheckoutIn(shipping_address_id=addr), "double-click-key"
            )
            return order.id

    ids = await asyncio.gather(*[attempt() for _ in range(5)])
    assert len(set(ids)) == 1
    assert (await stock(shop["skus"]["SP-1"])).reserved == 2


async def test_last_unit_race_via_checkout(shop, make_user):
    """10 customers check out the last 2 units at the same moment: exactly 2 orders exist."""
    vid = uuid.UUID(shop["skus"]["NT-A4"])  # 2 in stock
    users = []
    for i in range(10):
        user, _ = await make_user(f"racer{i}@example.com")
        async with SessionLocal() as s:
            from app.cart import service as cart_service
            from app.users.models import Address

            cart, _ = await cart_service.get_cart(s, user.id, None, create=True)
            await cart_service.add_item(s, cart, vid, 1)
            addr = Address(user_id=user.id, **{k: v for k, v in ADDR.items()}, country="IN")
            s.add(addr)
            await s.commit()
            users.append((user, addr.id))

    async def attempt(user, addr_id):
        async with SessionLocal() as s:
            try:
                await checkout.place_order(s, user, CheckoutIn(shipping_address_id=addr_id), uuid.uuid4().hex)
                return True
            except Exception as exc:
                assert getattr(exc, "code", None) == "INSUFFICIENT_INVENTORY", exc
                return False

    results = await asyncio.gather(*[attempt(u, a) for u, a in users])
    assert sum(results) == 2
    async with SessionLocal() as s:
        assert len(list(await s.scalars(select(Order.id)))) == 2
    inv = await stock(str(vid))
    assert (inv.on_hand, inv.reserved) == (2, 2)


async def test_price_change_guard_and_cart_problems(client, shop, customer):
    addr = await address(client, customer)
    r = await place(client, customer, addr)
    assert r.json()["error"]["code"] == "CART_NOT_READY"  # empty

    await add(client, customer, shop["skus"]["SP-1"])
    r = await place(client, customer, addr, expected_total_paise=1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "PRICE_CHANGED"
    assert r.json()["error"]["details"]["total_paise"] == 24900

    await client.patch(
        f"/api/v1/admin/products/{shop['products']['b']['id']}",
        json={"status": "ARCHIVED"},
        headers=shop["pm"],
    )
    r = await place(client, customer, addr)
    assert r.json()["error"]["code"] == "CART_NOT_READY"
    assert r.json()["error"]["details"][0]["issue"] == "UNAVAILABLE"


async def test_cannot_ship_to_someone_elses_address(client, shop, customer, make_user):
    _, other = await make_user("other@example.com")
    their_addr = await address(client, other)
    await add(client, customer, shop["skus"]["SP-1"])
    r = await place(client, customer, their_addr)
    assert r.status_code == 404


async def test_coupon_claimed_once_per_user_and_released_on_cancel(client, shop, customer, staff):
    mk = await staff("MARKETING_MANAGER")
    coupon = (
        await client.post(
            "/api/v1/admin/coupons",
            json={"code": "ONCE", "discount_type": "FIXED", "value": 5000},
            headers=mk,
        )
    ).json()
    addr = await address(client, customer)
    await add(client, customer, shop["skus"]["SP-1"])
    await client.post("/api/v1/cart/coupon", json={"code": "ONCE"}, headers=customer)
    order = (await place(client, customer, addr)).json()
    assert order["discount_paise"] == 5000 and order["coupon_code"] == "ONCE"
    assert order["items"][0]["discount_paise"] == 5000

    # Second order with the same coupon is refused (per_user_limit defaults to 1).
    r = await place(client, customer, addr)
    assert r.json()["error"]["code"] == "INVALID_COUPON"

    # Cancelling the unpaid order gives back both stock and the coupon use.
    r = await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer)
    assert r.json()["status"] == "CANCELLED"
    assert (await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer)).json()["error"][
        "code"
    ] == "CANNOT_CANCEL"
    assert (await stock(shop["skus"]["SP-1"])).reserved == 0
    assert (await client.get(f"/api/v1/admin/coupons/{coupon['id']}", headers=mk)).json()["times_used"] == 0
    assert (await place(client, customer, addr)).status_code == 201


async def test_global_coupon_limit_under_concurrency(shop, make_user, staff, client):
    mk = await staff("MARKETING_MANAGER")
    await client.post(
        "/api/v1/admin/coupons",
        json={"code": "FIRST3", "discount_type": "FIXED", "value": 100, "usage_limit": 3},
        headers=mk,
    )
    from app.cart import service as cart_service
    from app.users.models import Address

    entrants = []
    for i in range(8):
        user, _ = await make_user(f"c{i}@example.com")
        async with SessionLocal() as s:
            cart, _ = await cart_service.get_cart(s, user.id, None, create=True)
            await cart_service.add_item(s, cart, uuid.UUID(shop["skus"]["SP-1"]), 1)
            cart.coupon_code = "FIRST3"
            addr = Address(user_id=user.id, **ADDR, country="IN")
            s.add(addr)
            await s.commit()
            entrants.append((user, addr.id))

    async def attempt(user, addr_id):
        async with SessionLocal() as s:
            try:
                await checkout.place_order(s, user, CheckoutIn(shipping_address_id=addr_id), uuid.uuid4().hex)
                return True
            except Exception as exc:
                assert getattr(exc, "code", None) == "INVALID_COUPON", exc
                return False

    assert sum(await asyncio.gather(*[attempt(u, a) for u, a in entrants])) == 3
    async with SessionLocal() as s:
        assert (await s.scalar(select(Coupon).where(Coupon.code == "FIRST3"))).times_used == 3


async def test_first_order_coupon(client, shop, customer, staff, db):
    mk = await staff("MARKETING_MANAGER")
    await client.post(
        "/api/v1/admin/coupons",
        json={
            "code": "NEWBIE",
            "discount_type": "PERCENT",
            "value": 20,
            "first_order_only": True,
            "per_user_limit": 5,
        },
        headers=mk,
    )
    addr = await address(client, customer)
    await add(client, customer, shop["skus"]["SP-1"])
    assert (
        await client.post("/api/v1/cart/coupon", json={"code": "NEWBIE"}, headers=customer)
    ).status_code == 200
    first = (await place(client, customer, addr)).json()

    await db.execute(update(Order).where(Order.id == uuid.UUID(first["id"])).values(status="DELIVERED"))
    await db.commit()
    r = await client.post("/api/v1/cart/coupon", json={"code": "NEWBIE"}, headers=customer)
    assert r.json()["error"]["message"] == "This coupon is only valid on your first order"


async def test_unpaid_orders_expire_and_release_everything(client, shop, customer):
    addr = await address(client, customer)
    await add(client, customer, shop["skus"]["NT-A3"], 3)
    order = (await place(client, customer, addr)).json()

    async with SessionLocal() as s:
        assert await orders.expire_unpaid(s) == 0  # not due yet
        await s.execute(
            update(Order)
            .where(Order.id == uuid.UUID(order["id"]))
            .values(payment_due_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()
    async with SessionLocal() as s:
        assert await orders.expire_unpaid(s) == 1
        assert await orders.expire_unpaid(s) == 0  # idempotent

    o = (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()
    assert o["status"] == "CANCELLED" and [h["to_status"] for h in o["history"]] == [
        "PENDING_PAYMENT",
        "CANCELLED",
    ]
    inv = await stock(shop["skus"]["NT-A3"])
    assert (inv.on_hand, inv.reserved) == (5, 0)


async def test_order_listing_and_privacy(client, shop, customer, make_user):
    addr = await address(client, customer)
    await add(client, customer, shop["skus"]["SP-1"], 2)
    o1 = (await place(client, customer, addr)).json()
    o2 = (await place(client, customer, addr)).json()
    page = (await client.get("/api/v1/orders", params={"limit": 1}, headers=customer)).json()
    assert page["items"][0]["id"] == o2["id"] and page["items"][0]["item_count"] == 2
    page2 = (
        await client.get("/api/v1/orders", params={"cursor": page["next_cursor"]}, headers=customer)
    ).json()
    assert [o["id"] for o in page2["items"]] == [o1["id"]]

    _, other = await make_user("snoop@example.com")
    assert (await client.get(f"/api/v1/orders/{o1['id']}", headers=other)).status_code == 404
    assert (await client.post(f"/api/v1/orders/{o1['id']}/cancel", headers=other)).status_code == 404


async def test_idempotency_key_required_and_validated(client, shop, customer):
    addr = await address(client, customer)
    r = await client.post("/api/v1/checkout", json={"shipping_address_id": addr}, headers=customer)
    assert r.status_code == 422
    r = await client.post(
        "/api/v1/checkout",
        json={"shipping_address_id": addr},
        headers={**customer, "Idempotency-Key": "bad key!"},
    )
    assert r.status_code == 422


async def test_checkout_and_orders_require_login(client):
    r = await client.post(
        "/api/v1/checkout",
        json={"shipping_address_id": str(uuid.uuid4())},
        headers={"Idempotency-Key": "k" * 10},
    )
    assert r.status_code == 401
    assert (await client.get("/api/v1/orders")).status_code == 401
