import asyncio
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.cart import service as cart_service
from app.cart.models import CartItem
from app.core.database import SessionLocal
from app.notifications import service as notifications
from app.notifications.models import Notification
from app.users.models import User
from tests.integration.test_payments import checkout, paid_order


class Sender:
    def __init__(self, fail: bool = False):
        self.sent: list[tuple[str, str, str]] = []
        self.fail = fail

    async def send(self, to, subject, body):
        if self.fail:
            raise ConnectionError("smtp down")
        self.sent.append((to, subject, body))
        return f"<msg{len(self.sent)}@test>"


async def test_order_lifecycle_emails_are_queued_once(client, shop, customer, pay, outbox):
    order = await paid_order(client, customer, pay, shop["skus"]["SP-1"])
    assert await outbox.count("order_confirmed") == 1
    row = (await outbox.rows("order_confirmed"))[0]
    assert row.context["order_number"] == order["number"] and row.context["total"] == "₹249.00"

    pay.refund_mode = "processed"
    await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer)
    assert await outbox.count("order_cancelled") == 1
    assert (await outbox.rows("refund_processed"))[0].context["amount"] == "₹249.00"


async def test_unpaid_cancellation_is_silent(client, shop, customer, outbox):
    order = await checkout(client, customer, shop["skus"]["SP-1"])
    await client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer)
    assert await outbox.count("order_cancelled") == 0


async def test_drain_sends_renders_and_scrubs_secrets(client, outbox):
    await client.post(
        "/api/v1/auth/register",
        json={"email": "ada@example.com", "password": "correct-horse-1", "full_name": "Ada Lovelace"},
    )
    sender = Sender()
    assert await notifications.drain(sender) == 1
    to, subject, body = sender.sent[0]
    assert to == "ada@example.com" and subject == "Verify your email"
    assert body.startswith("Hi Ada,") and "verify-email?token=" in body
    row = (await outbox.rows("verify_email"))[0]
    assert row.status == "SENT" and row.subject == "Verify your email"
    assert row.context == {}  # the live token isn't kept once sent
    assert await notifications.drain(sender) == 0


async def test_retries_with_backoff_then_dead_letter_then_admin_retry(client, staff, outbox):
    support = await staff("CUSTOMER_SUPPORT")  # registering queues a verification email
    async with SessionLocal() as s:
        user = await s.scalar(select(User))
        await notifications.enqueue(
            s,
            "order_shipped",
            recipient="x@example.com",
            user_id=user.id,
            context={"name": "X", "order_number": "HSC-1", "order_url": "u"},
            dedupe_key="t1",
        )
        await s.commit()

    broken = Sender(fail=True)
    await notifications.drain(broken)
    row = next(r for r in await outbox.rows("order_shipped"))
    assert row.status == "PENDING" and row.attempts == 1 and "smtp down" in row.last_error
    assert row.next_attempt_at > datetime.now(UTC) + timedelta(seconds=20)  # backed off

    for _ in range(notifications.MAX_ATTEMPTS):
        async with SessionLocal() as s:  # fast-forward the backoff
            await s.execute(
                update(Notification).values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await s.commit()
        await notifications.drain(broken)
    row = next(r for r in await outbox.rows("order_shipped"))
    assert row.status == "FAILED" and row.attempts == notifications.MAX_ATTEMPTS

    dead = (
        await client.get("/api/v1/admin/notifications", params={"status": "FAILED"}, headers=support)
    ).json()["items"]
    assert {d["template"] for d in dead} == {"order_shipped", "verify_email"}
    shipped = next(d for d in dead if d["template"] == "order_shipped")
    assert (await client.post(f"/api/v1/admin/notifications/{shipped['id']}/retry", headers=support)).json()[
        "status"
    ] == "PENDING"
    # Security emails aren't resurrected: their token was scrubbed and may have expired.
    verify = next(d for d in dead if d["template"] == "verify_email")
    r = await client.post(f"/api/v1/admin/notifications/{verify['id']}/retry", headers=support)
    assert r.json()["error"]["code"] == "NOT_RETRYABLE"
    ok = Sender()
    await notifications.drain(ok)
    assert [s[1] for s in ok.sent] == ["Order HSC-1 is on its way"]


async def test_parallel_workers_deliver_each_notification_once(make_user):
    for i in range(30):
        async with SessionLocal() as s:
            await notifications.enqueue(
                s, "order_shipped", recipient=f"{i}@x.com", context={}, dedupe_key=f"p{i}"
            )
            await s.commit()
    sender = Sender()
    await asyncio.gather(*[notifications.drain(sender, batch=7) for _ in range(6)])
    await asyncio.gather(*[notifications.drain(sender, batch=7) for _ in range(6)])
    assert sorted(to for to, _, _ in sender.sent) == sorted(f"{i}@x.com" for i in range(30))


async def _age_cart(user_id, hours):
    async with SessionLocal() as s:
        cart, _ = await cart_service.get_cart(s, user_id, None)
        await s.execute(
            update(CartItem)
            .where(CartItem.cart_id == cart.id)
            .values(updated_at=datetime.now(UTC) - timedelta(hours=hours))
        )
        await s.commit()


async def test_abandoned_cart_reminder_once_and_respects_opt_out(client, shop, make_user, outbox):
    keen, keen_h = await make_user("keen@example.com")
    shy, shy_h = await make_user("shy@example.com")
    fresh, fresh_h = await make_user("fresh@example.com")
    for h in (keen_h, shy_h, fresh_h):
        await client.post(
            "/api/v1/cart/items", json={"variant_id": shop["skus"]["SP-1"], "quantity": 2}, headers=h
        )
    await client.patch("/api/v1/users/me", json={"preferences": {"marketing_emails": False}}, headers=shy_h)
    await _age_cart(keen.id, 30)
    await _age_cart(shy.id, 30)
    await _age_cart(fresh.id, 2)  # too recent

    async with SessionLocal() as s:
        assert await cart_service.queue_abandoned_cart_reminders(s) == 2
    async with SessionLocal() as s:
        assert await cart_service.queue_abandoned_cart_reminders(s) == 0  # once per stretch of activity
    rows = await outbox.rows("abandoned_cart")
    assert sorted(r.recipient for r in rows) == ["keen@example.com", "shy@example.com"]
    assert rows[0].context["item_count"] == 2

    sender = Sender()
    await notifications.drain(sender)
    assert [to for to, subj, _ in sender.sent if subj == "Still thinking it over?"] == ["keen@example.com"]
    assert (
        next(r for r in await outbox.rows("abandoned_cart") if r.recipient == "shy@example.com").status
        == "SKIPPED"
    )


async def test_template_override_validated_and_used(client, staff, outbox):
    mk = await staff("MARKETING_MANAGER")
    r = await client.put(
        "/api/v1/admin/notification-templates/order_shipped",
        json={"subject": "Hey $nmae", "body": "x"},
        headers=mk,
    )
    assert r.json()["error"]["code"] == "INVALID_TEMPLATE" and r.json()["error"]["details"]["unknown"] == [
        "nmae"
    ]

    r = await client.put(
        "/api/v1/admin/notification-templates/order_shipped",
        json={"subject": "🎨 $order_number shipped!", "body": "Yo $name, track: $order_url"},
        headers=mk,
    )
    assert r.json()["is_overridden"] is True
    async with SessionLocal() as s:
        await notifications.enqueue(
            s,
            "order_shipped",
            recipient="a@x.com",
            context={"name": "Ada", "order_number": "HSC-9", "order_url": "u"},
            dedupe_key="o1",
        )
        await s.commit()
    sender = Sender()
    await notifications.drain(sender)
    assert ("a@x.com", "🎨 HSC-9 shipped!", "Yo Ada, track: u") in sender.sent

    await client.delete("/api/v1/admin/notification-templates/order_shipped", headers=mk)
    listed = {
        t["code"]: t for t in (await client.get("/api/v1/admin/notification-templates", headers=mk)).json()
    }
    assert listed["order_shipped"]["is_overridden"] is False


async def test_customer_sees_only_own_notifications(client, make_user):
    a, ah = await make_user("a@example.com")
    _, bh = await make_user("b@example.com")
    async with SessionLocal() as s:
        await notifications.enqueue(
            s,
            "order_shipped",
            recipient="a@example.com",
            user_id=a.id,
            context={},
            dedupe_key=str(uuid.uuid4()),
        )
        await s.commit()
    assert len((await client.get("/api/v1/notifications", headers=ah)).json()["items"]) == 1
    assert (await client.get("/api/v1/notifications", headers=bh)).json()["items"] == []
