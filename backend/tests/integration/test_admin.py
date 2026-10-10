import csv
import io
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.audit.models import AuditLog
from app.core.database import SessionLocal
from app.inventory.models import InventoryTransaction
from tests.integration.test_catalog import PNG, create_product, setup_taxonomy, variant
from tests.integration.test_payments import paid_order


async def audit_rows() -> list[AuditLog]:
    async with SessionLocal() as s:
        return list(await s.scalars(select(AuditLog).order_by(AuditLog.created_at)))


# ---------- Audit ----------


async def test_admin_mutations_are_audited_with_redaction(client, staff, customer, storage):
    pm = await staff("PRODUCT_MANAGER")
    r = await client.post("/api/v1/admin/categories", json={"name": "Prints", "api_token": "abc"}, headers=pm)
    assert r.status_code == 201
    await client.get("/api/v1/admin/categories", headers=pm)  # reads aren't audited
    await client.post("/api/v1/admin/categories", json={"name": "Nope"}, headers=customer)  # denied attempt

    rows = await audit_rows()
    ok, denied = rows
    assert ok.action == "POST /api/v1/admin/categories" and ok.status_code == 201
    assert ok.actor_email == "product_manager@staff.example.com" and ok.actor_roles == ["PRODUCT_MANAGER"]
    assert ok.request_body == {"json": {"name": "Prints", "api_token": "[REDACTED]"}}
    assert ok.request_id and ok.target_type == "categories"
    assert denied.status_code == 403 and denied.actor_email == "customer@example.com"

    await setup_taxonomy(client, pm)
    p = await create_product(client, pm, "Pic", [variant("P1", "A3", "Black", 100)])
    await client.post(
        f"/api/v1/admin/products/{p['id']}/media", files={"file": ("a.png", PNG, "image/png")}, headers=pm
    )
    upload = (await audit_rows())[-1]
    assert upload.target_id == p["id"] and upload.target_type == "products"
    assert upload.request_body["bytes"] > 0 and "json" not in upload.request_body  # shape, not content


async def test_audit_log_api(client, staff):
    admin = await staff("ADMIN")
    pm = await staff("PRODUCT_MANAGER")
    cat = (await client.post("/api/v1/admin/categories", json={"name": "Prints"}, headers=pm)).json()
    await client.patch(f"/api/v1/admin/categories/{cat['id']}", json={"name": "Fine Prints"}, headers=pm)
    page = (
        await client.get("/api/v1/admin/audit-logs", params={"target_id": cat["id"]}, headers=admin)
    ).json()
    assert [i["action"] for i in page["items"]] == ["PATCH /api/v1/admin/categories/{category_id}"]
    assert (await client.get("/api/v1/admin/audit-logs", headers=pm)).status_code == 403


# ---------- Dashboard & analytics ----------


async def test_dashboard(client, shop, customer, pay, staff):
    await paid_order(client, customer, pay, shop["skus"]["NT-A4"], 2)  # NT-A4 had 2 -> now 0 left
    await client.post(
        "/api/v1/reviews", json={"product_id": shop["products"]["b"]["id"], "rating": 4}, headers=customer
    )
    support = await staff("CUSTOMER_SUPPORT")
    d = (await client.get("/api/v1/admin/dashboard", headers=support)).json()
    assert d["revenue"]["today"]["orders"] == 1 and d["revenue"]["today"]["gross_paise"] == 80000 + 9900
    assert d["needs_attention"]["to_fulfil"] == 1 and d["needs_attention"]["reviews_to_moderate"] == 1
    assert d["inventory"]["out_of_stock_variants"] == 1
    assert d["customers"]["total"] == 1  # staff accounts excluded
    assert d["products"]["active"] == 2
    assert (await client.get("/api/v1/admin/dashboard", headers=customer)).status_code == 403


async def test_sales_analytics_net_of_refunds(client, shop, customer, pay, staff):
    om = await staff("ORDER_MANAGER")
    o1 = await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    await client.post(
        f"/api/v1/admin/orders/{o1['id']}/refunds",
        json={"amount_paise": 5000, "reason": "scuffed"},
        headers={**om, "Idempotency-Key": "refund-analytics-1"},
    )
    mk = await staff("MARKETING_MANAGER")
    today = datetime.now(UTC).astimezone().date()
    series = (
        await client.get(
            "/api/v1/admin/analytics/sales",
            params={"from": str(today - timedelta(days=6)), "to": str(today + timedelta(days=1))},
            headers=mk,
        )
    ).json()
    assert len(series) == 8  # continuous, zero-filled
    totals = {k: sum(p[k] for p in series) for k in ("orders", "gross_paise", "refunds_paise", "net_paise")}
    assert totals == {"orders": 2, "gross_paise": 49800, "refunds_paise": 5000, "net_paise": 44800}

    top = (
        await client.get("/api/v1/admin/analytics/top-products", params={"by": "units"}, headers=mk)
    ).json()
    assert top[0]["title"] == "Sticker Pack" and top[0]["units"] == 2
    stats = (await client.get("/api/v1/admin/analytics/customers", headers=mk)).json()
    assert stats == {"buyers": 1, "repeat_buyers": 1, "repeat_rate": 1.0, "orders_per_buyer": 2.0}
    r = await client.get(
        "/api/v1/admin/analytics/sales", params={"from": "2020-01-01", "to": "2026-01-01"}, headers=mk
    )
    assert r.json()["error"]["code"] == "INVALID_RANGE"


# ---------- Customers & staff ----------


async def test_customer_admin(client, shop, customer, pay, staff):
    support = await staff("CUSTOMER_SUPPORT")
    admin = await staff("ADMIN")
    await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    rows = (await client.get("/api/v1/admin/customers", headers=support)).json()["items"]
    assert [r["email"] for r in rows] == ["customer@example.com"]  # staff excluded
    assert rows[0]["order_count"] == 1 and rows[0]["total_spent_paise"] == 24900
    assert (await client.get("/api/v1/admin/customers", params={"q": "CUSTOMER@"}, headers=support)).json()[
        "items"
    ]
    assert not (await client.get("/api/v1/admin/customers", params={"q": "nobody"}, headers=support)).json()[
        "items"
    ]

    detail = (await client.get(f"/api/v1/admin/customers/{rows[0]['id']}", headers=support)).json()
    assert len(detail["addresses"]) == 1 and len(detail["recent_orders"]) == 1

    url = f"/api/v1/admin/customers/{rows[0]['id']}"
    assert (
        await client.patch(url, json={"is_active": False, "reason": "fraud"}, headers=support)
    ).status_code == 403
    assert (
        await client.patch(url, json={"is_active": False, "reason": "chargeback fraud"}, headers=admin)
    ).json()["is_active"] is False
    assert (
        await client.get("/api/v1/users/me", headers=customer)
    ).status_code == 401  # signed out everywhere


async def test_role_management(client, staff, make_user, db):
    boss = await staff("SUPER_ADMIN")
    admin = await staff("ADMIN")
    newbie, newbie_h = await make_user("newbie@example.com")
    url = f"/api/v1/admin/users/{newbie.id}/roles"
    assert (
        await client.put(url, json={"roles": ["ADMIN"]}, headers=admin)
    ).status_code == 403  # ADMIN can't grant
    r = await client.put(url, json={"roles": ["ORDER_MANAGER", "CUSTOMER_SUPPORT"]}, headers=boss)
    assert r.json()["roles"] == ["CUSTOMER_SUPPORT", "ORDER_MANAGER"]
    assert (
        await client.get("/api/v1/admin/orders", headers=newbie_h)
    ).status_code == 200  # effective immediately

    me = next(
        u
        for u in (await client.get("/api/v1/admin/users", headers=boss)).json()
        if "SUPER_ADMIN" in u["roles"]
    )
    r = await client.put(f"/api/v1/admin/users/{me['id']}/roles", json={"roles": ["ADMIN"]}, headers=boss)
    assert r.json()["error"]["code"] == "SELF_LOCKOUT"


# ---------- Banners ----------


async def test_banners(client, staff):
    mk = await staff("MARKETING_MANAGER")
    base = {"title": "Diwali Sale", "image_url": "https://cdn.test/d.jpg", "placement": "HOME_HERO"}
    bad = await client.post(
        "/api/v1/admin/banners", json={**base, "link_url": "javascript:alert(1)"}, headers=mk
    )
    assert bad.status_code == 422
    live = (
        await client.post(
            "/api/v1/admin/banners", json={**base, "link_url": "/collection/diwali"}, headers=mk
        )
    ).json()
    soon = datetime.now(UTC) + timedelta(days=2)
    await client.post(
        "/api/v1/admin/banners",
        json={**base, "title": "Coming soon", "starts_at": soon.isoformat()},
        headers=mk,
    )
    await client.post(
        "/api/v1/admin/banners", json={**base, "title": "Strip", "placement": "HOME_STRIP"}, headers=mk
    )

    shown = (await client.get("/api/v1/banners")).json()
    assert [b["title"] for b in shown] == ["Diwali Sale"]  # scheduled one hidden, other placement filtered
    await client.put(
        f"/api/v1/admin/banners/{live['id']}", json={**base, "title": "Diwali Sale — 30% off"}, headers=mk
    )
    assert (await client.get("/api/v1/banners")).json()[0][
        "title"
    ] == "Diwali Sale — 30% off"  # cache invalidated


# ---------- CSV ----------


def read_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def to_csv(rows: list[dict]) -> bytes:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(dict.fromkeys(k for r in rows for k in r)))
    w.writeheader()
    w.writerows(rows)
    return out.getvalue().encode()


async def upload(client, headers, rows, dry_run):
    return await client.post(
        "/api/v1/admin/products/import",
        params={"dry_run": str(dry_run).lower()},
        files={"file": ("products.csv", to_csv(rows), "text/csv")},
        headers=headers,
    )


async def test_csv_round_trip_update_and_create(client, staff):
    pm = await staff("PRODUCT_MANAGER")
    await setup_taxonomy(client, pm)
    await create_product(
        client, pm, '=HYPERLINK("http://evil")', [variant("EVIL-1", "A4", "None", 10000, stock=3)]
    )
    await create_product(client, pm, "Neon", [variant("NEON-A3", "A3", "Black", 150000, stock=5)])

    r = await client.get("/api/v1/admin/products/export.csv", headers=pm)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    rows = read_csv(r.text)
    evil = next(x for x in rows if x["sku"] == "EVIL-1")
    assert evil["product_title"].startswith("'=")  # neutralised for Excel/Sheets
    neon = next(x for x in rows if x["sku"] == "NEON-A3")
    assert neon["price"] == "1500.00" and neon["options"] == "frame=Black; size=A3" and neon["on_hand"] == "5"

    neon.update(price="1299.50", on_hand="12")
    new_row = {
        **neon,
        "product_slug": "tokyo-rain",
        "product_title": "Tokyo Rain",
        "sku": "RAIN-A2",
        "options": "size=A2; frame=White",
        "price": "999",
        "on_hand": "7",
        "status": "ACTIVE",
        "category_slug": "movie-posters",
        "tags": "rain|city",
    }
    payload = [*rows, new_row]

    dry = (await upload(client, pm, payload, True)).json()
    assert dry["dry_run"] is True and dry["products_created"] == 1 and dry["stock_adjusted"] == 1
    assert (await client.get("/api/v1/products/tokyo-rain")).status_code == 404  # nothing saved

    real = (await upload(client, pm, payload, False)).json()
    assert real["products_updated"] == 2 and real["variants_created"] == 1
    neon_after = (await client.get("/api/v1/products/neon")).json()["variants"][0]
    assert neon_after["price_paise"] == 129950
    rain = (await client.get("/api/v1/products/tokyo-rain")).json()
    assert rain["category"]["slug"] == "movie-posters" and {t["slug"] for t in rain["tags"]} == {
        "rain",
        "city",
    }
    assert (await client.get("/api/v1/search", params={"q": "rain"})).json()["items"][0][
        "slug"
    ] == "tokyo-rain"
    evil_after = (await client.get("/api/v1/admin/products", params={"q": "EVIL-1"}, headers=pm)).json()[
        "items"
    ][0]
    assert evil_after["title"].startswith("=HYPERLINK")  # our own escaping undone on re-import

    async with SessionLocal() as s:
        reasons = list(
            await s.scalars(
                select(InventoryTransaction.reason).where(InventoryTransaction.reason == "CSV import")
            )
        )
    assert reasons == ["CSV import"]


async def test_csv_errors_reported_per_row_and_nothing_saved(client, staff):
    pm = await staff("PRODUCT_MANAGER")
    await setup_taxonomy(client, pm)
    await create_product(client, pm, "Existing", [variant("TAKEN-1", "A4", "None", 100)])
    base = {
        "product_slug": "new-one",
        "product_title": "New One",
        "sku": "OK-1",
        "price": "100",
        "options": "size=A4",
    }
    rows = [
        base,
        {**base, "sku": "BAD-PRICE", "price": "12.345"},
        {**base, "sku": "BAD-OPT", "options": "size A3"},
        {**base, "sku": "OK-1"},  # duplicate SKU in file
    ]
    r = await upload(client, pm, rows, False)
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_CSV"
    errors = {e["row"]: e["error"] for e in r.json()["error"]["details"]["errors"]}
    assert "2 decimal" in errors[3] and "size=A3" in errors[4] and "more than once" in errors[2]

    # Business-rule errors (second stage) are also all-or-nothing.
    rows = [
        {**base, "product_slug": "fine", "product_title": "Fine", "sku": "FINE-1"},
        {**base, "product_slug": "thief", "product_title": "Thief", "sku": "TAKEN-1"},
        {**base, "product_slug": "lost", "product_title": "Lost", "sku": "LOST-1", "category_slug": "nope"},
    ]
    r = await upload(client, pm, rows, False)
    details = r.json()["error"]["details"]["errors"]
    assert {e["product_slug"] for e in details} == {"thief", "lost"}
    assert (await client.get("/api/v1/admin/products", params={"q": "FINE-1"}, headers=pm)).json()[
        "items"
    ] == []

    r = await client.post(
        "/api/v1/admin/products/import",
        files={"file": ("x.csv", b"title,price\nA,1\n", "text/csv")},
        headers=pm,
    )
    assert r.json()["error"]["details"]["missing_columns"] == ["product_slug", "product_title", "sku"]
