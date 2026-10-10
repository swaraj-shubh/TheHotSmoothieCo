import asyncio

from fastapi import Depends
from sqlalchemy import update

from app.auth.dependencies import require_roles
from app.main import app
from app.users import repository
from app.users.models import RoleName, User

PW = "correct-horse-battery"


async def register(client, email="Art@Example.com", password=PW):
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password, "full_name": "Ada"}
    )
    assert r.status_code == 201, r.text
    return r.json()


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_register_login_me(client, outbox):
    data = await register(client)
    assert data["user"]["email"] == "art@example.com"  # normalised
    assert data["user"]["email_verified"] is False
    assert "password_hash" not in data["user"]

    r = await client.post("/api/v1/auth/login", json={"email": "ART@example.com", "password": PW})
    assert r.status_code == 200
    me = await client.get("/api/v1/users/me", headers=bearer(r.json()))
    assert me.json()["full_name"] == "Ada"


async def test_duplicate_email_rejected_even_concurrently(client, outbox):
    payload = {"email": "dup@example.com", "password": PW, "full_name": "X"}
    results = await asyncio.gather(*[client.post("/api/v1/auth/register", json=payload) for _ in range(5)])
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409, 409, 409, 409]
    assert results[[r.status_code for r in results].index(409)].json()["error"]["code"] == "EMAIL_TAKEN"


async def test_bad_login_does_not_reveal_which_part_is_wrong(client, outbox):
    await register(client)
    wrong_pw = await client.post(
        "/api/v1/auth/login", json={"email": "art@example.com", "password": "nope-nope"}
    )
    no_user = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope-nope"}
    )
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


async def test_refresh_rotates_and_late_reuse_kills_session(client, outbox, db):
    tokens = await register(client)
    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200
    new = r1.json()
    assert new["refresh_token"] != tokens["refresh_token"]

    # Replaying the old token *after* the grace window = theft signal: the session is revoked...
    from datetime import UTC, datetime, timedelta

    from app.auth.models import UserSession

    await db.execute(update(UserSession).values(last_used_at=datetime.now(UTC) - timedelta(minutes=5)))
    await db.commit()
    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert replay.status_code == 401
    # ...so the legitimately rotated token and its access token are dead too.
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]})
    ).status_code == 401
    assert (await client.get("/api/v1/users/me", headers=bearer(new))).status_code == 401


async def test_parallel_refreshes_within_grace_window_keep_the_session(client, outbox):
    """A page firing several requests at once must not log the customer out."""
    tokens = await register(client)
    results = await asyncio.gather(
        *[
            client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
            for _ in range(5)
        ]
    )
    assert all(r.status_code == 200 for r in results)
    rotated = [r.json()["refresh_token"] for r in results if r.json()["refresh_token"]]
    assert len(rotated) == 1  # exactly one winner rotates; the others get an access token only
    for r in results:
        assert (await client.get("/api/v1/users/me", headers=bearer(r.json()))).status_code == 200
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": rotated[0]})).status_code == 200


async def test_logout_invalidates_access_token_immediately(client, outbox):
    tokens = await register(client)
    assert (await client.post("/api/v1/auth/logout", headers=bearer(tokens))).status_code == 204
    assert (await client.get("/api/v1/users/me", headers=bearer(tokens))).status_code == 401
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401


async def test_sessions_listing_and_logout_all(client, outbox):
    t1 = await register(client)
    t2 = (await client.post("/api/v1/auth/login", json={"email": "art@example.com", "password": PW})).json()
    sessions = (await client.get("/api/v1/auth/sessions", headers=bearer(t1))).json()
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1

    await client.post("/api/v1/auth/logout-all", headers=bearer(t2))
    assert (await client.get("/api/v1/users/me", headers=bearer(t1))).status_code == 401


async def test_deactivated_account(client, outbox, db):
    tokens = await register(client)
    await db.execute(update(User).values(is_active=False))
    await db.commit()
    assert (await client.get("/api/v1/users/me", headers=bearer(tokens))).status_code == 401
    r = await client.post("/api/v1/auth/login", json={"email": "art@example.com", "password": PW})
    assert r.status_code == 403 and r.json()["error"]["code"] == "ACCOUNT_DISABLED"


async def test_email_verification_is_single_use(client, outbox):
    tokens = await register(client)
    token = await outbox.token("verify_email")
    assert (await client.post("/api/v1/auth/verify-email", json={"token": token})).status_code == 204
    again = await client.post("/api/v1/auth/verify-email", json={"token": token})
    assert again.status_code == 400 and again.json()["error"]["code"] == "INVALID_TOKEN"
    assert (await client.get("/api/v1/users/me", headers=bearer(tokens))).json()["email_verified"] is True


async def test_password_reset_flow_revokes_sessions(client, outbox):
    tokens = await register(client)
    r = await client.post("/api/v1/auth/forgot-password", json={"email": "art@example.com"})
    assert r.status_code == 202
    # Unknown emails get the identical response and send nothing.
    sent_before = await outbox.count()
    r2 = await client.post("/api/v1/auth/forgot-password", json={"email": "ghost@example.com"})
    assert r2.status_code == 202 and r2.json() == r.json() and await outbox.count() == sent_before

    token = await outbox.token("password_reset")
    r = await client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": "brand-new-pass"}
    )
    assert r.status_code == 204
    assert (await client.get("/api/v1/users/me", headers=bearer(tokens))).status_code == 401
    assert (
        await client.post("/api/v1/auth/login", json={"email": "art@example.com", "password": PW})
    ).status_code == 401
    ok = await client.post(
        "/api/v1/auth/login", json={"email": "art@example.com", "password": "brand-new-pass"}
    )
    assert ok.status_code == 200


async def test_change_password_keeps_current_session_only(client, outbox):
    t1 = await register(client)
    t2 = (await client.post("/api/v1/auth/login", json={"email": "art@example.com", "password": PW})).json()
    r = await client.post(
        "/api/v1/auth/change-password",
        json={"current_password": PW, "new_password": "another-pass-1"},
        headers=bearer(t1),
    )
    assert r.status_code == 204
    assert (await client.get("/api/v1/users/me", headers=bearer(t1))).status_code == 200
    assert (await client.get("/api/v1/users/me", headers=bearer(t2))).status_code == 401


async def test_login_is_rate_limited(client, outbox):
    codes = [
        (
            await client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "whatever1"})
        ).status_code
        for _ in range(11)
    ]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


async def test_validation_errors_use_standard_envelope(client):
    r = await client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "short", "full_name": ""}
    )
    body = r.json()
    assert r.status_code == 422 and body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert {d["field"] for d in body["error"]["details"]} == {"email", "password", "full_name"}


async def test_garbage_token_rejected(client):
    r = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_TOKEN"


async def test_rbac_enforced_on_backend(client, outbox, db):
    @app.get("/_test/inventory-only", dependencies=[Depends(require_roles(RoleName.INVENTORY_MANAGER))])
    async def _probe():
        return {"ok": True}

    tokens = await register(client)
    assert (await client.get("/_test/inventory-only", headers=bearer(tokens))).status_code == 403

    user = await repository.get_by_email(db, "art@example.com")
    user.roles = await repository.get_roles(db, [RoleName.SUPER_ADMIN])
    await db.commit()
    assert (await client.get("/_test/inventory-only", headers=bearer(tokens))).status_code == 200


async def test_soft_delete_frees_email(client, outbox):
    tokens = await register(client)
    assert (await client.delete("/api/v1/users/me", headers=bearer(tokens))).status_code == 204
    assert (
        await client.post("/api/v1/auth/login", json={"email": "art@example.com", "password": PW})
    ).status_code == 401
    await register(client)  # same email can sign up again
