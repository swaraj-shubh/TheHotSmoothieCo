import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.core.database import SessionLocal
from app.inventory import service as inv
from app.inventory.models import Inventory, InventoryReservation, InventoryTransaction
from tests.integration.test_catalog import create_product, setup_taxonomy, variant


@pytest.fixture
async def product(client, staff):
    pm = await staff("PRODUCT_MANAGER")
    await setup_taxonomy(client, pm)
    p = await create_product(
        client,
        pm,
        "Stocked",
        [variant("ST-A3", "A3", "Black", 1000, stock=5), variant("ST-A4", "A4", "None", 500, stock=3)],
    )
    return {v["sku"]: uuid.UUID(v["id"]) for v in p["variants"]}


async def stock(variant_id) -> Inventory:
    async with SessionLocal() as s:
        return await s.get(Inventory, variant_id)


async def test_100_buyers_5_units_never_oversells(product):
    """Spec §32: 100 concurrent checkouts for the last 5 units -> exactly 5 succeed."""
    vid = product["ST-A3"]

    async def attempt():
        async with SessionLocal() as s:
            try:
                await inv.reserve(s, uuid.uuid4(), {vid: 1}, ttl_seconds=900)
                await s.commit()
                return True
            except inv.InsufficientInventory:
                await s.rollback()
                return False

    results = await asyncio.gather(*[attempt() for _ in range(100)])
    assert sum(results) == 5
    row = await stock(vid)
    assert (row.on_hand, row.reserved, row.available) == (5, 5, 0)


async def test_multi_line_reserve_is_all_or_nothing(product):
    order = uuid.uuid4()
    async with SessionLocal() as s:
        with pytest.raises(inv.InsufficientInventory) as e:
            await inv.reserve(s, order, {product["ST-A3"]: 2, product["ST-A4"]: 4}, ttl_seconds=900)
        await s.rollback()
    assert e.value.details == [{"variant_id": str(product["ST-A4"]), "requested": 4, "available": 3}]
    assert (await stock(product["ST-A3"])).reserved == 0  # the line that fit was rolled back too


async def test_reserve_commit_release_are_idempotent(product):
    vid, order = product["ST-A3"], uuid.uuid4()
    async with SessionLocal() as s:
        await inv.reserve(s, order, {vid: 2}, ttl_seconds=900)
        await inv.reserve(s, order, {vid: 2}, ttl_seconds=900)  # retry: no double hold
        await s.commit()
    assert (await stock(vid)).reserved == 2

    async with SessionLocal() as s:
        assert await inv.commit_reservation(s, order) == 1
        assert await inv.commit_reservation(s, order) == 0  # duplicate webhook -> no-op
        assert await inv.release_reservation(s, order) == 0  # can't release after commit
        await s.commit()
    row = await stock(vid)
    assert (row.on_hand, row.reserved, row.sold) == (3, 0, 2)

    async with SessionLocal() as s:
        types = list(
            await s.scalars(
                select(InventoryTransaction.type)
                .where(InventoryTransaction.variant_id == vid)
                .order_by(InventoryTransaction.created_at)
            )
        )
    assert types == ["INITIAL", "RESERVE", "COMMIT"]


async def test_release_and_expiry_sweep(product):
    vid = product["ST-A4"]
    cancelled, abandoned = uuid.uuid4(), uuid.uuid4()
    async with SessionLocal() as s:
        await inv.reserve(s, cancelled, {vid: 1}, ttl_seconds=900)
        await inv.reserve(s, abandoned, {vid: 2}, ttl_seconds=900)
        await s.commit()
    assert (await stock(vid)).available == 0

    async with SessionLocal() as s:
        await inv.release_reservation(s, cancelled)
        await s.execute(
            update(InventoryReservation)
            .where(InventoryReservation.reference_id == abandoned)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await s.commit()

    async with SessionLocal() as s:
        refs = await inv.expired_references(s)
        assert refs == [abandoned]
        for ref in refs:
            await inv.release_reservation(s, ref, expired=True)
        await s.commit()
    row = await stock(vid)
    assert (row.reserved, row.available) == (0, 3)


async def test_db_constraint_is_last_line_of_defence(product):
    from sqlalchemy.exc import IntegrityError

    async with SessionLocal() as s:
        with pytest.raises(IntegrityError):
            await s.execute(
                update(Inventory).where(Inventory.variant_id == product["ST-A3"]).values(reserved=99)
            )


async def test_admin_adjust_history_and_low_stock(client, staff, product):
    im = await staff("INVENTORY_MANAGER")
    vid = product["ST-A3"]

    async with SessionLocal() as s:
        await inv.reserve(s, uuid.uuid4(), {vid: 4}, ttl_seconds=900)
        await s.commit()

    r = await client.post(
        f"/api/v1/admin/inventory/{vid}/adjust", json={"set_to": 2, "reason": "stock count"}, headers=im
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_ADJUSTMENT"  # 4 are reserved
    r = await client.post(
        f"/api/v1/admin/inventory/{vid}/adjust",
        json={"delta": 20, "reason": "restock from printer"},
        headers=im,
    )
    assert r.status_code == 204
    r = await client.post(
        f"/api/v1/admin/inventory/{vid}/adjust", json={"delta": 5, "set_to": 3, "reason": "both"}, headers=im
    )
    assert r.status_code == 422

    rows = (await client.get("/api/v1/admin/inventory", headers=im)).json()["items"]
    a3 = next(r for r in rows if r["sku"] == "ST-A3")
    assert (a3["on_hand"], a3["reserved"], a3["available"], a3["low_stock"]) == (25, 4, 21, False)

    low = (await client.get("/api/v1/admin/inventory", params={"low_stock": "true"}, headers=im)).json()[
        "items"
    ]
    assert [r["sku"] for r in low] == ["ST-A4"]  # 3 available <= threshold 5

    hist = (
        await client.get(f"/api/v1/admin/inventory/{vid}/history", params={"limit": 2}, headers=im)
    ).json()
    assert [h["type"] for h in hist["items"]] == ["ADJUSTMENT", "RESERVE"]
    assert hist["items"][0]["reason"] == "restock from printer" and hist["next_cursor"]
    older = (
        await client.get(
            f"/api/v1/admin/inventory/{vid}/history", params={"cursor": hist["next_cursor"]}, headers=im
        )
    ).json()
    assert [h["type"] for h in older["items"]] == ["INITIAL"]


async def test_inventory_admin_rbac(client, staff, product):
    marketing = await staff("MARKETING_MANAGER")
    r = await client.post(
        f"/api/v1/admin/inventory/{product['ST-A3']}/adjust",
        json={"delta": 1, "reason": "nope"},
        headers=marketing,
    )
    assert r.status_code == 403
