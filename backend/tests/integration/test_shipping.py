import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from app.core.database import SessionLocal
from app.inventory.models import Inventory
from app.orders.models import OrderStatusHistory
from tests.conftest import SHIP_TOKEN
from tests.integration.test_payments import paid_order


@pytest.fixture
async def om(staff):
    return await staff("ORDER_MANAGER")


async def track(client, awb, status, scans, token=SHIP_TOKEN):
    body = json.dumps({"awb": awb, "current_status": status, "scans": scans}).encode()
    return await client.post("/api/v1/webhooks/shipping", content=body, headers={"x-api-key": token})


async def ship_order(client, om, order_id) -> dict:
    r = await client.post(f"/api/v1/admin/orders/{order_id}/shipments", headers=om)
    assert r.status_code == 200, r.text
    return r.json()


async def status(client, headers, order_id) -> str:
    return (await client.get(f"/api/v1/orders/{order_id}", headers=headers)).json()["status"]


async def test_fulfilment_to_delivery(client, shop, customer, pay, ship, om):
    order = await paid_order(client, customer, pay, shop["skus"]["NT-A3"], 2)
    s = await ship_order(client, om, order["id"])
    assert s["status"] == "AWB_ASSIGNED" and s["awb"] and s["label_url"]
    assert await status(client, customer, order["id"]) == "PACKED"
    _, package, _ = ship.created[0]
    assert package.weight_grams == 500  # 2 x default 250 g
    r = await client.post(f"/api/v1/admin/orders/{order['id']}/shipments", headers=om)
    assert r.json()["error"]["code"] == "CANNOT_SHIP"  # no double booking

    scans = [
        {"date": "2026-10-07 10:00:00", "status": "PICKED UP", "activity": "Picked up", "location": "Delhi"}
    ]
    assert (await track(client, s["awb"], "IN TRANSIT", scans)).status_code == 200
    assert (await track(client, s["awb"], "IN TRANSIT", scans)).json()["status"] == "PROCESSED"  # duplicate
    assert await status(client, customer, order["id"]) == "SHIPPED"

    scans.append(
        {
            "date": "2026-10-09 15:30:00",
            "status": "DELIVERED",
            "activity": "Delivered",
            "location": "Bengaluru",
        }
    )
    await track(client, s["awb"], "DELIVERED", scans)
    o = (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()
    assert o["status"] == "DELIVERED"
    # SHIPPED -> DELIVERED directly: no invented OUT_FOR_DELIVERY step.
    assert [h["to_status"] for h in o["history"]][-3:] == ["PACKED", "SHIPPED", "DELIVERED"]

    tracking = (await client.get(f"/api/v1/shipping/orders/{order['id']}", headers=customer)).json()
    assert [e["raw_status"] for e in tracking[0]["events"]] == ["Picked up", "Delivered"]  # deduped

    # Late/out-of-order scans never move a delivered order backwards.
    await track(client, s["awb"], "IN TRANSIT", scans)
    assert await status(client, customer, order["id"]) == "DELIVERED"


async def test_shipping_webhook_auth(client, ship):
    assert (await track(client, "AWB1", "DELIVERED", [], token="wrong")).status_code == 400
    r = await track(client, "UNKNOWN", "DELIVERED", [])
    assert r.status_code == 200 and r.json()["status"] == "IGNORED"


async def test_awb_failure_is_retryable(client, shop, customer, pay, ship, om):
    order = await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    ship.fail_awb = True
    s = await ship_order(client, om, order["id"])
    assert s["status"] == "CREATED" and s["awb"] is None
    assert await status(client, customer, order["id"]) == "PROCESSING"
    ship.fail_awb = False
    s = (await client.post(f"/api/v1/admin/shipments/{s['id']}/awb", headers=om)).json()
    assert s["status"] == "AWB_ASSIGNED" and len(ship.created) == 1  # not re-booked
    assert await status(client, customer, order["id"]) == "PACKED"


async def test_cancellation_rules_once_shipping_started(client, shop, customer, pay, ship, om):
    vid = shop["skus"]["NT-A4"]
    order = await paid_order(client, customer, pay, vid, 2)
    await ship_order(client, om, order["id"])
    r = await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer)
    assert r.json()["error"]["code"] == "CANNOT_CANCEL"  # customer: too late

    r = await client.post(
        f"/api/v1/admin/orders/{order['id']}/cancel", json={"reason": "out of ink"}, headers=om
    )
    assert r.json()["status"] == "REFUNDED"  # fake gateway settles instantly
    assert ship.cancelled == ["SRO1"] and r.json()["shipments"][0]["status"] == "CANCELLED"
    async with SessionLocal() as s:
        assert (await s.get(Inventory, uuid.UUID(vid))).on_hand == 2


async def test_return_flow(client, shop, customer, pay, ship, om):
    vid = shop["skus"]["SP-1"]
    order = await paid_order(client, customer, pay, vid, 3)
    s = await ship_order(client, om, order["id"])
    await track(client, s["awb"], "DELIVERED", [])

    ret = await client.post(
        f"/api/v1/orders/{order['id']}/return", json={"reason": "Colours look off"}, headers=customer
    )
    assert ret.status_code == 201
    again = await client.post(
        f"/api/v1/orders/{order['id']}/return", json={"reason": "again"}, headers=customer
    )
    assert again.json()["error"]["code"] == "RETURN_NOT_ALLOWED"
    assert await status(client, customer, order["id"]) == "RETURN_REQUESTED"

    rid = ret.json()["id"]
    approved = (await client.post(f"/api/v1/admin/returns/{rid}/approve", json={}, headers=om)).json()
    assert approved["status"] == "APPROVED" and approved["shipment_id"] and ship.created[-1][2] is True

    received = await client.post(f"/api/v1/admin/returns/{rid}/receive", json={"restock": True}, headers=om)
    assert received.json()["status"] == "RECEIVED" and received.json()["restocked"]
    detail = (await client.get(f"/api/v1/admin/orders/{order['id']}", headers=om)).json()
    assert detail["status"] == "REFUNDED" and detail["refunds"][0]["amount_paise"] == order["total_paise"]
    async with SessionLocal() as db:
        assert (await db.get(Inventory, uuid.UUID(vid))).on_hand == 100


async def test_return_rejected_and_window(client, shop, customer, pay, ship, om):
    order = await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    s = await ship_order(client, om, order["id"])
    await track(client, s["awb"], "DELIVERED", [])
    rid = (
        await client.post(
            f"/api/v1/orders/{order['id']}/return", json={"reason": "changed mind"}, headers=customer
        )
    ).json()["id"]
    r = await client.post(f"/api/v1/admin/returns/{rid}/reject", json={"note": "Opened item"}, headers=om)
    assert r.json()["status"] == "REJECTED"
    assert await status(client, customer, order["id"]) == "DELIVERED"

    async with SessionLocal() as db:
        await db.execute(
            update(OrderStatusHistory)
            .where(
                OrderStatusHistory.order_id == uuid.UUID(order["id"]),
                OrderStatusHistory.to_status == "DELIVERED",
            )
            .values(created_at=datetime.now(UTC) - timedelta(days=30))
        )
        await db.commit()
    r = await client.post(f"/api/v1/orders/{order['id']}/return", json={"reason": "late"}, headers=customer)
    assert r.json()["error"]["code"] == "RETURN_NOT_ALLOWED" and "7 days" in r.json()["error"]["message"]


async def test_rto_marks_order_returned(client, shop, customer, pay, ship, om):
    order = await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    s = await ship_order(client, om, order["id"])
    await track(client, s["awb"], "IN TRANSIT", [])
    await track(client, s["awb"], "RTO DELIVERED", [])
    assert await status(client, customer, order["id"]) == "RETURNED"


async def test_support_can_view_but_not_act(client, shop, customer, pay, staff):
    support = await staff("CUSTOMER_SUPPORT")
    order = await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    rows = (await client.get("/api/v1/admin/orders", params={"q": order["number"]}, headers=support)).json()[
        "items"
    ]
    assert [r["id"] for r in rows] == [order["id"]]
    r = await client.post(
        f"/api/v1/admin/orders/{order['id']}/cancel", json={"reason": "nope"}, headers=support
    )
    assert r.status_code == 403


async def test_serviceability(client, ship):
    r = (await client.get("/api/v1/shipping/serviceability", params={"pincode": "560001"})).json()
    assert r == {"pincode": "560001", "serviceable": True, "estimated_days": 2}
    assert (await client.get("/api/v1/shipping/serviceability", params={"pincode": "999999"})).json()[
        "serviceable"
    ] is False
    assert (await client.get("/api/v1/shipping/serviceability", params={"pincode": "12"})).status_code == 422
