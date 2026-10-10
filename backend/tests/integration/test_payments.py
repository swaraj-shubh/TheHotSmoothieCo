import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.database import SessionLocal
from app.inventory.models import Inventory
from app.orders import service as orders
from app.orders.models import Order
from tests.conftest import RZP_SECRET, RZP_WEBHOOK_SECRET
from tests.integration.test_addresses import ADDR


async def checkout(client, headers, variant_id, qty=1) -> dict:
    addr = (await client.post("/api/v1/users/me/addresses", json=ADDR, headers=headers)).json()["id"]
    await client.post("/api/v1/cart/items", json={"variant_id": variant_id, "quantity": qty}, headers=headers)
    r = await client.post(
        "/api/v1/checkout",
        json={"shipping_address_id": addr},
        headers={**headers, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def webhook(client, event: str, payment=None, refund=None, event_id=None):
    payload = {"event": event, "payload": {}}
    if payment:
        payload["payload"]["payment"] = {
            "entity": {
                "id": payment.id,
                "order_id": payment.order_id,
                "status": payment.status,
                "amount": payment.amount_paise,
                "method": payment.method,
            }
        }
    if refund:
        payload["payload"]["refund"] = {
            "entity": {
                "id": refund.id,
                "payment_id": refund.payment_id,
                "status": "processed",
                "amount": refund.amount_paise,
                "notes": refund.notes,
            }
        }
    body = json.dumps(payload).encode()
    sig = hmac.new(RZP_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return await client.post(
        "/api/v1/webhooks/razorpay",
        content=body,
        headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": event_id or uuid.uuid4().hex},
    )


async def stock(vid) -> Inventory:
    async with SessionLocal() as s:
        return await s.get(Inventory, uuid.UUID(vid))


async def test_pay_via_client_callback_then_duplicate_webhook(client, shop, customer, pay):
    vid = shop["skus"]["NT-A3"]
    order = await checkout(client, customer, vid, 2)
    init = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)).json()
    again = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)).json()
    assert (
        init["provider_order_id"] == again["provider_order_id"]
        and init["amount_paise"] == order["total_paise"]
    )

    p = pay.pay(init["provider_order_id"])
    bad = await client.post(
        f"/api/v1/payments/orders/{order['id']}/verify",
        headers=customer,
        json={"provider_order_id": p.order_id, "provider_payment_id": p.id, "signature": "0" * 64},
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_PAYMENT_SIGNATURE"

    sig = hmac.new(RZP_SECRET.encode(), f"{p.order_id}|{p.id}".encode(), hashlib.sha256).hexdigest()
    ok = await client.post(
        f"/api/v1/payments/orders/{order['id']}/verify",
        headers=customer,
        json={"provider_order_id": p.order_id, "provider_payment_id": p.id, "signature": sig},
    )
    assert ok.json()["order_status"] == "CONFIRMED" and ok.json()["payment_status"] == "CAPTURED"
    inv = await stock(vid)
    assert (inv.on_hand, inv.reserved, inv.sold) == (3, 0, 2)
    assert (await client.get("/api/v1/cart", headers=customer)).json()["items"] == []

    # Webhook for the same payment, delivered twice: no double confirm, no double stock movement.
    r1 = await webhook(client, "payment.captured", p, event_id="evt_1")
    r2 = await webhook(client, "payment.captured", p, event_id="evt_1")
    assert r1.status_code == r2.status_code == 200
    inv = await stock(vid)
    assert (inv.on_hand, inv.sold) == (3, 2)
    o = (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()
    assert [h["to_status"] for h in o["history"]] == ["PENDING_PAYMENT", "CONFIRMED"]


async def test_bad_webhook_signature_rejected(client, pay):
    r = await client.post(
        "/api/v1/webhooks/razorpay", content=b"{}", headers={"X-Razorpay-Signature": "nope"}
    )
    assert r.status_code == 400


async def test_late_payment_is_refunded_automatically(client, shop, customer, pay):
    pay.refund_mode = "pending"  # real gateways settle refunds asynchronously
    order = await checkout(client, customer, shop["skus"]["SP-1"])
    init = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)).json()
    async with SessionLocal() as s:
        await s.execute(
            update(Order)
            .where(Order.id == uuid.UUID(order["id"]))
            .values(payment_due_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()
    async with SessionLocal() as s:
        assert await orders.expire_unpaid(s) == 1

    p = pay.pay(init["provider_order_id"])
    assert (await webhook(client, "order.paid", p)).status_code == 200
    o = (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()
    assert o["status"] == "REFUND_PENDING" and len(pay.refunds) == 1

    # Refund confirmation webhook completes it.
    assert (await webhook(client, "refund.processed", refund=pay.refunds[0])).status_code == 200
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()[
        "status"
    ] == "REFUNDED"


async def test_cancel_paid_order_restocks_and_refunds_once(client, shop, customer, pay):
    pay.refund_mode = "pending"
    vid = shop["skus"]["NT-A4"]
    order = await checkout(client, customer, vid, 2)
    init = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)).json()
    await webhook(client, "payment.captured", pay.pay(init["provider_order_id"]))
    assert (await stock(vid)).on_hand == 0

    r = await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer)
    assert r.json()["status"] == "REFUND_PENDING"
    assert (await stock(vid)).on_hand == 2 and len(pay.refunds) == 1
    again = await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer)
    assert again.json()["error"]["code"] == "CANNOT_CANCEL" and len(pay.refunds) == 1


async def test_payments_unavailable_without_credentials(client, shop, customer):
    order = await checkout(client, customer, shop["skus"]["SP-1"])
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)
    assert r.status_code == 503 and r.json()["error"]["code"] == "PAYMENTS_UNAVAILABLE"


async def paid_order(client, headers, pay, variant_id, qty=1) -> dict:
    order = await checkout(client, headers, variant_id, qty)
    init = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=headers)).json()
    assert (await webhook(client, "payment.captured", pay.pay(init["provider_order_id"]))).status_code == 200
    return order


async def test_failed_attempt_allows_retry_and_authorised_blocks_expiry(client, shop, customer, pay):
    order = await checkout(client, customer, shop["skus"]["SP-1"])
    init = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)).json()
    await webhook(client, "payment.failed", pay.pay(init["provider_order_id"], status="failed"))
    status = (await client.get(f"/api/v1/payments/orders/{order['id']}", headers=customer)).json()
    assert status["order_status"] == "PENDING_PAYMENT"  # customer can try another card

    await webhook(client, "payment.authorized", pay.pay(init["provider_order_id"], status="authorized"))
    async with SessionLocal() as s:
        await s.execute(
            update(Order)
            .where(Order.id == uuid.UUID(order["id"]))
            .values(payment_due_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await s.commit()
    async with SessionLocal() as s:
        assert await orders.expire_unpaid(s) == 0  # money in flight: never auto-cancelled
    o = (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()
    assert o["status"] == "PAYMENT_PROCESSING"


async def test_staff_refund_idempotent_and_capped(client, shop, customer, pay, staff):
    om = await staff("ORDER_MANAGER")
    order = await paid_order(client, customer, pay, shop["skus"]["SP-1"])  # ₹150 + ₹99 shipping
    url = f"/api/v1/admin/orders/{order['id']}/refunds"

    r1 = await client.post(
        url,
        json={"amount_paise": 5000, "reason": "scuffed"},
        headers={**om, "Idempotency-Key": "refund-key-1"},
    )
    r2 = await client.post(
        url,
        json={"amount_paise": 5000, "reason": "scuffed"},
        headers={**om, "Idempotency-Key": "refund-key-1"},
    )
    assert r1.status_code == 200 and r1.json()["id"] == r2.json()["id"] and len(pay.refunds) == 1
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()[
        "status"
    ] == "CONFIRMED"

    over = await client.post(
        url,
        json={"amount_paise": 99999, "reason": "too much"},
        headers={**om, "Idempotency-Key": "refund-key-2"},
    )
    assert over.json()["error"]["code"] == "REFUND_NOT_ALLOWED"

    rest = await client.post(
        url, json={"reason": "goodwill"}, headers={**om, "Idempotency-Key": "refund-key-3"}
    )
    assert rest.json()["amount_paise"] == order["total_paise"] - 5000
    detail = (await client.get(f"/api/v1/admin/orders/{order['id']}", headers=om)).json()
    assert detail["status"] == "REFUNDED" and len(detail["refunds"]) == 2


async def test_ambiguous_refund_reconciled_by_webhook(client, shop, customer, pay, staff):
    om = await staff("ORDER_MANAGER")
    order = await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    pay.refund_mode = "ambiguous"
    r = (
        await client.post(
            f"/api/v1/admin/orders/{order['id']}/refunds",
            json={"reason": "cancelled by phone"},
            headers={**om, "Idempotency-Key": "refund-timeout-1"},
        )
    ).json()
    assert r["status"] == "PENDING" and "awaiting" in r["failure_reason"]

    # Still counted: a second full refund is refused while the first is unresolved.
    again = await client.post(
        f"/api/v1/admin/orders/{order['id']}/refunds",
        json={"reason": "retry"},
        headers={**om, "Idempotency-Key": "refund-timeout-2"},
    )
    assert again.json()["error"]["code"] == "REFUND_NOT_ALLOWED"

    # Gateway did process it; its webhook carries our refund id in notes.
    from app.payments.provider import ProviderRefund

    payment_id = (await client.get(f"/api/v1/admin/orders/{order['id']}", headers=om)).json()["payment"][
        "provider_payment_id"
    ]
    gw = ProviderRefund("rfnd_late", payment_id, "processed", r["amount_paise"], {"refund_id": r["id"]})
    assert (await webhook(client, "refund.processed", refund=gw)).status_code == 200
    detail = (await client.get(f"/api/v1/admin/orders/{order['id']}", headers=om)).json()
    assert detail["refunds"][0]["status"] == "PROCESSED" and detail["status"] == "REFUNDED"


async def test_webhook_handler_crash_is_recorded_and_retried(client, shop, customer, pay, monkeypatch):
    from sqlalchemy import select

    from app.payments import service as payments
    from app.payments.models import WebhookEvent

    order = await checkout(client, customer, shop["skus"]["SP-1"])
    init = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)).json()
    p = pay.pay(init["provider_order_id"])
    real = payments.apply_payment

    async def boom(*a, **kw):
        raise RuntimeError("db hiccup")

    monkeypatch.setattr(payments, "apply_payment", boom)
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    # Like a real server: return the 500 instead of re-raising into the test.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as raw:
        r = await webhook(raw, "payment.captured", p, event_id="evt_crash")
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR"  # gateway will redeliver
    async with SessionLocal() as s:
        ev = await s.scalar(select(WebhookEvent).where(WebhookEvent.event_id == "evt_crash"))
        assert ev.status == "FAILED" and "db hiccup" in ev.error

    monkeypatch.setattr(payments, "apply_payment", real)
    assert (await webhook(client, "payment.captured", p, event_id="evt_crash")).status_code == 200
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()[
        "status"
    ] == "CONFIRMED"


async def test_initiate_guards(client, shop, customer, pay, make_user):
    order = await checkout(client, customer, shop["skus"]["SP-1"])
    _, other = await make_user("other@example.com")
    assert (
        await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=other)
    ).status_code == 404
    await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer)
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)
    assert r.json()["error"]["code"] == "ORDER_NOT_PAYABLE"


async def test_dev_payment_provider_flow(client, shop, customer, monkeypatch):
    from app.core.config import Settings, get_settings

    monkeypatch.setattr(get_settings(), "payments_provider", "dev")
    order = await checkout(client, customer, shop["skus"]["SP-1"])
    init = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)).json()
    assert init["provider"] == "dev" and init["amount_paise"] == order["total_paise"]

    url = f"/api/v1/payments/orders/{order['id']}/simulate"
    declined = (await client.post(url, json={"outcome": "failure"}, headers=customer)).json()
    assert declined["order_status"] == "PENDING_PAYMENT"  # can retry
    paid = (await client.post(url, json={"outcome": "success"}, headers=customer)).json()
    assert paid == {"order_id": order["id"], "order_status": "CONFIRMED", "payment_status": "CAPTURED"}
    again = (await client.post(url, json={"outcome": "success"}, headers=customer)).json()
    assert again["order_status"] == "CONFIRMED"  # idempotent

    with pytest.raises(ValueError, match="PAYMENTS_PROVIDER=dev"):
        Settings(environment="production", jwt_secret="x" * 40, payments_provider="dev")


async def test_simulate_endpoint_hidden_with_real_gateway(client, shop, customer, pay):
    order = await checkout(client, customer, shop["skus"]["SP-1"])
    await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)
    r = await client.post(f"/api/v1/payments/orders/{order['id']}/simulate", json={}, headers=customer)
    assert r.status_code == 404
