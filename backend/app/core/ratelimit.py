import structlog
from fastapi import Request
from redis.exceptions import RedisError

from app.core.clientip import client_ip, end_user_ip, is_trusted_bff
from app.core.config import get_settings
from app.core.exceptions import RateLimited
from app.core.redis import redis

log = structlog.get_logger()


def rate_limit(name: str, limit: int, window_seconds: int):
    """Per-client fixed-window limit, shared across all API instances via Redis.

    Usage: `dependencies=[Depends(rate_limit("login", 10, 60))]`.
    Fails open if Redis is down: availability beats limiting; the outage is logged.
    """

    async def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        if is_trusted_bff(request.scope) and not end_user_ip(request.scope):
            return  # server-to-server (e.g. catalog cache refills): not a visitor, don't throttle
        client = client_ip(request.scope)
        key = f"rl:{name}:{client}"
        try:
            async with redis.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, window_seconds, nx=True)
                count, _ = await pipe.execute()
        except RedisError:
            log.warning("rate_limit_unavailable", limiter=name)
            return
        if count > limit:
            raise RateLimited()

    return dependency
