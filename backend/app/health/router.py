import asyncio
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import text

from app.core.database import engine
from app.core.redis import WORKER_HEARTBEAT_KEY, redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
@router.get("/live")
async def live():
    """Process is up. Never touches dependencies, so a DB blip doesn't get the container killed."""
    return {"status": "ok"}


async def _check_db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _check(name: str, coro) -> tuple[str, str]:
    try:
        await asyncio.wait_for(coro, timeout=2)
        return name, "ok"
    except Exception:  # any failure means "not ready"; details stay in logs, not the response
        return name, "unavailable"


@router.get("/ready")
async def ready():
    """Dependencies reachable. Load balancers should route traffic only when this is 200."""
    checks = dict(await asyncio.gather(_check("database", _check_db()), _check("redis", redis.ping())))
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "degraded", "checks": checks}, status_code=200 if ok else 503
    )


@router.get("/worker")
async def worker():
    """For uptime monitors: is the background worker alive? (heartbeat every ~1 s, 60 s TTL)"""
    try:
        beat = await redis.get(WORKER_HEARTBEAT_KEY)
    except RedisError:
        beat = None
    age = int(time.time()) - int(beat) if beat else None
    ok = age is not None and age < 30
    return JSONResponse(
        {"status": "ok" if ok else "down", "last_heartbeat_seconds_ago": age}, status_code=200 if ok else 503
    )
