"""Phase 7 hardening: abuse limits, dependency failures, and N+1 regression guards."""

import time
from contextlib import contextmanager

import pytest
from redis.exceptions import ConnectionError as RedisDown
from sqlalchemy import event

from app.auth import service as auth
from app.core.database import SessionLocal, engine
from app.core.exceptions import RateLimited
from app.core.redis import WORKER_HEARTBEAT_KEY, redis
from app.health import router as health
from tests.conftest import PASSWORD
from tests.integration.test_catalog import create_product, setup_taxonomy, variant
from tests.integration.test_payments import paid_order

# ---------- Abuse limits ----------


async def test_oversized_json_rejected_before_parsing(client):
    big = b'{"email": "' + b"a" * (2 * 1024 * 1024) + b'"}'
    r = await client.post("/api/v1/auth/login", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_chunked_body_that_lies_about_size_is_cut_off(client):
    async def chunks():
        for _ in range(40):
            yield b"x" * 64 * 1024  # 2.5 MB, no Content-Length

    r = await client.post(
        "/api/v1/auth/login", content=chunks(), headers={"content-type": "application/json"}
    )
    assert r.status_code == 413


async def test_per_account_lockout_independent_of_ip(make_user):
    await make_user("victim@example.com")
    async with SessionLocal() as db:
        for _ in range(auth.LOGIN_FAILURE_LIMIT):
            with pytest.raises(auth.InvalidCredentials):
                await auth.login(db, "victim@example.com", "wrong-password", None, None)
        with pytest.raises(RateLimited) as locked:
            await auth.login(db, "victim@example.com", PASSWORD, None, None)  # even the right password
        assert locked.value.code == "LOGIN_LOCKED"
        # Unknown emails lock identically: no account enumeration through the lockout.
        for _ in range(auth.LOGIN_FAILURE_LIMIT):
            with pytest.raises(auth.InvalidCredentials):
                await auth.login(db, "ghost@example.com", "x", None, None)
        with pytest.raises(RateLimited):
            await auth.login(db, "ghost@example.com", "x", None, None)


async def test_successful_login_resets_failure_count(make_user):
    await make_user("forgetful@example.com")
    async with SessionLocal() as db:
        for _ in range(auth.LOGIN_FAILURE_LIMIT - 1):
            with pytest.raises(auth.InvalidCredentials):
                await auth.login(db, "forgetful@example.com", "wrong-password", None, None)
        await auth.login(db, "forgetful@example.com", PASSWORD, None, None)
        for _ in range(auth.LOGIN_FAILURE_LIMIT - 1):  # fresh budget
            with pytest.raises(auth.InvalidCredentials):
                await auth.login(db, "forgetful@example.com", "wrong-password", None, None)


# ---------- Dependency failures ----------


async def test_storefront_and_login_survive_redis_outage(client, shop, make_user, monkeypatch):
    await make_user("calm@example.com")

    async def down(*a, **kw):
        raise RedisDown("redis is down")

    for name in ("get", "set", "delete", "incr"):
        monkeypatch.setattr(redis, name, down)
    monkeypatch.setattr(redis, "pipeline", lambda *a, **kw: (_ for _ in ()).throw(RedisDown("down")))

    assert (await client.get("/api/v1/categories")).status_code == 200  # cache falls through to Postgres
    assert (await client.get("/api/v1/products")).json()["items"]
    r = await client.post("/api/v1/auth/login", json={"email": "calm@example.com", "password": PASSWORD})
    assert r.status_code == 200  # rate limits and lockout fail open


async def test_readiness_reports_unavailable_dependency(client, monkeypatch):
    async def db_down():
        raise OSError("connection refused")

    monkeypatch.setattr(health, "_check_db", db_down)
    r = await client.get("/health/ready")
    assert r.status_code == 503 and r.json()["checks"] == {"database": "unavailable", "redis": "ok"}
    assert (
        await client.get("/health/live")
    ).status_code == 200  # liveness unaffected: don't restart for a DB blip


async def test_worker_health(client):
    assert (await client.get("/health/worker")).status_code == 503
    await redis.set(WORKER_HEARTBEAT_KEY, int(time.time()), ex=60)
    assert (await client.get("/health/worker")).json()["status"] == "ok"


# ---------- N+1 guards ----------


@contextmanager
def count_queries():
    counter = {"n": 0}

    def before(*_):
        counter["n"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", before)
    try:
        yield counter
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", before)


async def queries_for(client, url, **kw) -> int:
    with count_queries() as c:
        r = await client.get(url, **kw)
        assert r.status_code == 200, r.text
    return c["n"]


async def test_listing_and_detail_query_counts_dont_grow_with_data(client, staff):
    pm = await staff("PRODUCT_MANAGER")
    await setup_taxonomy(client, pm)
    await create_product(
        client, pm, "P0", [variant("Q0-A", "A3", "Black", 100), variant("Q0-B", "A4", "None", 100)]
    )
    small_list = await queries_for(client, "/api/v1/products")
    small_detail = await queries_for(client, "/api/v1/products/p0")
    small_search = await queries_for(client, "/api/v1/search", params={"q": "p"})

    for i in range(1, 12):
        variants = [
            variant(f"Q{i}-{s}", s, f, 100 + i) for s, f in (("A3", "Black"), ("A4", "None"), ("A2", "White"))
        ]
        await create_product(client, pm, f"P{i}", variants)
    assert await queries_for(client, "/api/v1/products") == small_list
    assert await queries_for(client, "/api/v1/products/p11") == small_detail  # 3 variants vs 2: same count
    assert await queries_for(client, "/api/v1/search", params={"q": "p"}) == small_search


async def test_cart_and_order_query_counts_are_bounded(client, shop, customer, pay, staff):
    await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["SP-1"]}, headers=customer)
    one_line = await queries_for(client, "/api/v1/cart", headers=customer)
    await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["NT-A3"]}, headers=customer)
    await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["NT-A4"]}, headers=customer)
    assert await queries_for(client, "/api/v1/cart", headers=customer) == one_line

    om = await staff("ORDER_MANAGER")
    await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    few = await queries_for(client, "/api/v1/admin/orders", headers=om)
    for _ in range(4):
        await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    assert await queries_for(client, "/api/v1/admin/orders", headers=om) == few
    assert await queries_for(client, "/api/v1/orders", headers=customer) <= 8
