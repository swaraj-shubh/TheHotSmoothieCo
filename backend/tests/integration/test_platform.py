from app.core.redis import redis


async def test_liveness_and_readiness(client):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    r = await client.get("/health/ready")
    assert r.status_code == 200 and r.json()["checks"] == {"database": "ok", "redis": "ok"}


async def test_request_id_and_security_headers(client):
    r = await client.get("/health/live", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"
    assert r.headers["x-content-type-options"] == "nosniff"
    # Header injection attempts are replaced with a fresh ID.
    r = await client.get("/health/live", headers={"X-Request-ID": "bad id\\r\\n"})
    assert r.headers["x-request-id"] != "bad id\\r\\n"


async def test_unknown_route_uses_error_envelope(client):
    r = await client.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["success"] is False


async def test_rate_limiter_fails_open_when_redis_down(client, monkeypatch):
    from redis.exceptions import ConnectionError

    def broken(*a, **kw):
        raise ConnectionError("down")

    monkeypatch.setattr(redis, "pipeline", broken)
    r = await client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "whatever1"})
    assert r.status_code == 401  # request processed normally, not 500
