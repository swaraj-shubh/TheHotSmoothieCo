"""One customer, start to finish, through the public HTTP API only (gateways faked at the network
edge). If this passes, the platform's critical path works end to end: browse -> search -> cart ->
register/verify -> checkout -> pay -> ship -> deliver -> review -> return -> refund."""

import hashlib
import hmac
import json

from app.notifications import service as notifications
from tests.conftest import RZP_SECRET, SHIP_TOKEN
from tests.integration.test_catalog import PNG, setup_taxonomy, variant
from tests.integration.test_payments import webhook


class Inbox:
    def __init__(self):
        self.mail: list[tuple[str, str, str]] = []

    async def send(self, to, subject, body):
        self.mail.append((to, subject, body))
        return None

    def subjects(self, to: str) -> list[str]:
        return [s for t, s, _ in self.mail if t == to]


async def test_customer_journey(client, staff, outbox, pay, ship, storage):
    inbox = Inbox()
    admin = await staff("ADMIN")

    # --- Merchandising: catalog with a photo and a launch coupon ---------------------------------
    posters, _, _ = await setup_taxonomy(client, admin)
    product = (
        await client.post(
            "/api/v1/admin/products",
            headers=admin,
            json={
                "title": "Monsoon Mumbai",
                "status": "ACTIVE",
                "category_id": posters["id"],
                "tags": ["rain"],
                "short_description": "Marine Drive in the rain",
                "variants": [
                    variant("MM-A3-BLK", "A3", "Black", 149900, stock=3),
                    variant("MM-A4", "A4", "None", 59900, stock=10),
                ],
            },
        )
    ).json()
    await client.post(
        f"/api/v1/admin/products/{product['id']}/media",
        headers=admin,
        files={"file": ("m.png", PNG, "image/png")},
        data={"alt_text": "Marine Drive"},
    )
    await client.post(
        "/api/v1/admin/coupons",
        headers=admin,
        json={"code": "MONSOON10", "discount_type": "PERCENT", "value": 10},
    )

    # --- Guest browses, searches, adds to cart ---------------------------------------------------
    assert (await client.get("/api/v1/categories")).json()[0]["slug"] == "posters"
    found = (await client.get("/api/v1/search", params={"q": "mumbai rain"})).json()["items"]
    assert found[0]["slug"] == "monsoon-mumbai" and found[0]["thumbnail_url"]
    detail = (await client.get("/api/v1/products/monsoon-mumbai")).json()
    a3 = next(v for v in detail["variants"] if v["sku"] == "MM-A3-BLK")
    guest = (await client.post("/api/v1/cart/items", json={"variant_id": a3["id"], "quantity": 1})).json()
    cart_token = guest["cart_token"]

    # --- Registers, verifies email, guest cart follows them ---------------------------------------
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "riya@example.com", "password": "monsoon-lover-1", "full_name": "Riya Sharma"},
    )
    me = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    await notifications.drain(inbox)
    assert inbox.subjects("riya@example.com") == ["Verify your email"]
    verify_token = inbox.mail[-1][2].split("token=")[1].split()[0]
    assert (await client.post("/api/v1/auth/verify-email", json={"token": verify_token})).status_code == 204
    cart = (await client.post("/api/v1/cart/merge", headers={**me, "X-Cart-Token": cart_token})).json()
    assert cart["item_count"] == 1

    # --- Checkout with coupon, pays via the Razorpay widget ---------------------------------------
    addr = (
        await client.post(
            "/api/v1/users/me/addresses",
            headers=me,
            json={
                "full_name": "Riya Sharma",
                "phone": "+919812345678",
                "line1": "Flat 4, Sea View",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postal_code": "400020",
            },
        )
    ).json()
    cart = (await client.post("/api/v1/cart/coupon", json={"code": "monsoon10"}, headers=me)).json()
    assert cart["totals"]["discount_paise"] == 14990 and cart["totals"]["total_paise"] == 134910
    order = (
        await client.post(
            "/api/v1/checkout",
            headers={**me, "Idempotency-Key": "riya-checkout-001"},
            json={"shipping_address_id": addr["id"], "expected_total_paise": cart["totals"]["total_paise"]},
        )
    ).json()
    widget = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=me)).json()
    payment = pay.pay(widget["provider_order_id"])
    signature = hmac.new(
        RZP_SECRET.encode(), f"{payment.order_id}|{payment.id}".encode(), hashlib.sha256
    ).hexdigest()
    paid = (
        await client.post(
            f"/api/v1/payments/orders/{order['id']}/verify",
            headers=me,
            json={
                "provider_order_id": payment.order_id,
                "provider_payment_id": payment.id,
                "signature": signature,
            },
        )
    ).json()
    assert paid["order_status"] == "CONFIRMED"
    assert (await webhook(client, "payment.captured", payment)).status_code == 200  # late webhook: harmless
    assert (await client.get("/api/v1/cart", headers=me)).json()["items"] == []

    # --- Studio ships it; courier delivers ---------------------------------------------------------
    shipment = (await client.post(f"/api/v1/admin/orders/{order['id']}/shipments", headers=admin)).json()
    for status in ("IN TRANSIT", "DELIVERED"):
        body = json.dumps({"awb": shipment["awb"], "current_status": status, "scans": []}).encode()
        await client.post("/api/v1/webhooks/shipping", content=body, headers={"x-api-key": SHIP_TOKEN})
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=me)).json()["status"] == "DELIVERED"

    # --- Leaves a verified review ------------------------------------------------------------------
    review = (
        await client.post(
            "/api/v1/reviews",
            headers=me,
            json={
                "product_id": product["id"],
                "rating": 5,
                "title": "Stunning",
                "body": "Colours pop on my wall",
            },
        )
    ).json()
    assert review["verified_purchase"] is True
    await client.post(f"/api/v1/admin/reviews/{review['id']}/approve", json={}, headers=admin)
    public = (await client.get("/api/v1/products/monsoon-mumbai/reviews")).json()["items"]
    assert public[0]["author"] == "Riya S." and public[0]["verified_purchase"]

    # --- Changes her mind: return -> refund ---------------------------------------------------------
    ret = (
        await client.post(
            f"/api/v1/orders/{order['id']}/return", json={"reason": "Frame colour clashes"}, headers=me
        )
    ).json()
    await client.post(f"/api/v1/admin/returns/{ret['id']}/approve", json={}, headers=admin)
    await client.post(f"/api/v1/admin/returns/{ret['id']}/receive", json={"restock": True}, headers=admin)
    final = (await client.get(f"/api/v1/orders/{order['id']}", headers=me)).json()
    assert final["status"] == "REFUNDED"
    assert [h["to_status"] for h in final["history"]] == [
        "PENDING_PAYMENT",
        "CONFIRMED",
        "PROCESSING",
        "PACKED",
        "SHIPPED",
        "DELIVERED",
        "RETURN_REQUESTED",
        "RETURNED",
        "REFUND_PENDING",
        "REFUNDED",
    ]
    stock = (await client.get("/api/v1/products/monsoon-mumbai")).json()
    assert next(v for v in stock["variants"] if v["sku"] == "MM-A3-BLK")["max_purchasable"] == 3  # restocked

    # --- She heard about every step; staff actions are on record -----------------------------------
    await notifications.drain(inbox)
    assert inbox.subjects("riya@example.com")[1:] == [
        f"Order {order['number']} confirmed",
        f"Order {order['number']} is on its way",
        f"Order {order['number']} delivered",
        "Refund of ₹1,349.10 processed",
    ]
    audit = (
        await client.get("/api/v1/admin/audit-logs", params={"target_id": order["id"]}, headers=admin)
    ).json()
    assert {a["action"].split(" ")[0] for a in audit["items"]} == {"POST"}
    dashboard = (await client.get("/api/v1/admin/dashboard", headers=admin)).json()
    assert dashboard["revenue"]["today"]["net_paise"] == 0  # paid, then fully refunded
