import json
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from redis.exceptions import RedisError

from app.core.redis import redis

log = structlog.get_logger()


async def cached(key: str, ttl: int, loader: Callable[[], Awaitable[Any]]) -> Any:
    """Read-through JSON cache. Postgres stays the source of truth: any Redis failure
    just falls through to the loader."""
    try:
        hit = await redis.get(key)
        if hit is not None:
            return json.loads(hit)
    except RedisError:
        log.warning("cache_read_failed", key=key)
    value = await loader()
    try:
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
    except RedisError:
        log.warning("cache_write_failed", key=key)
    return value


async def invalidate(*keys: str) -> None:
    if not keys:
        return
    try:
        await redis.delete(*keys)
    except RedisError:
        # TTL bounds the staleness if this fails.
        log.warning("cache_invalidate_failed", keys=keys)
