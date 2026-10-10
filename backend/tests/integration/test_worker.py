import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.auth.models import UserToken
from app.cart.models import Cart
from app.core.database import SessionLocal, engine
from app.orders.models import Order
from app.workers import jobs
from app.workers.runner import Job, run_job
from tests.integration.test_payments import checkout, webhook


async def test_job_runs_on_one_worker_at_a_time():
    calls = []

    async def work():
        calls.append(1)
        return 1

    job = Job("exclusive-test", 60, work)
    async with engine.connect() as other_worker:
        await other_worker.scalar(select(func.pg_try_advisory_lock(job.lock_key)))
        assert await run_job(job) is False  # someone else holds it
        await other_worker.scalar(select(func.pg_advisory_unlock(job.lock_key)))
    assert await run_job(job) is True and calls == [1]
    assert await run_job(job) is True  # lock was released after the run


async def test_failing_job_never_crashes_the_worker():
    async def boom():
        raise RuntimeError("provider down")

    assert await run_job(Job("boom-test", 60, boom)) is True  # logged + reported, not raised


async def test_optional_integrations_are_skipped_when_unconfigured():
    assert await jobs.sync_shipments() == 0
    assert await jobs.reconcile_payments() == 0


async def test_cleanup_removes_only_stale_data(client, shop, customer, make_user):
    stale = (await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["SP-1"]})).json()
    live = (await client.post("/api/v1/cart/items", json={"variant_id": shop["skus"]["SP-1"]})).json()
    user, _ = await make_user("u@example.com")
    long_ago = datetime.now(UTC) - timedelta(days=45)
    async with SessionLocal() as s:
        await s.execute(update(Cart).where(Cart.id == uuid.UUID(stale["id"])).values(updated_at=long_ago))
        from app.cart.models import CartItem

        await s.execute(
            update(CartItem).where(CartItem.cart_id == uuid.UUID(stale["id"])).values(updated_at=long_ago)
        )
        s.add(UserToken(user_id=user.id, purpose="VERIFY_EMAIL", token_hash="x" * 64, expires_at=long_ago))
        await s.commit()

    assert await jobs.cleanup() >= 2
    async with SessionLocal() as s:
        assert await s.get(Cart, uuid.UUID(stale["id"])) is None
        assert await s.get(Cart, uuid.UUID(live["id"])) is not None
        assert (
            await s.scalar(
                select(func.count()).select_from(UserToken).where(UserToken.token_hash == "x" * 64)
            )
            == 0
        )


async def test_reconcile_confirms_payment_whose_capture_webhook_was_lost(client, shop, customer, pay):
    order = await checkout(client, customer, shop["skus"]["SP-1"])
    init = (await client.post(f"/api/v1/payments/orders/{order['id']}/initiate", headers=customer)).json()
    authorised = pay.pay(init["provider_order_id"], status="authorized")
    await webhook(client, "payment.authorized", authorised)
    async with SessionLocal() as s:
        await s.execute(
            update(Order)
            .where(Order.id == uuid.UUID(order["id"]))
            .values(updated_at=datetime.now(UTC) - timedelta(hours=2))
        )
        await s.commit()

    # Gateway captured it, but the payment.captured webhook never reached us.
    from dataclasses import replace

    pay.payments[authorised.id] = replace(authorised, status="captured")
    from app.payments import service as payments

    async with SessionLocal() as s:
        assert await payments.reconcile_processing(s, pay) == 1
    assert (await client.get(f"/api/v1/orders/{order['id']}", headers=customer)).json()[
        "status"
    ] == "CONFIRMED"
