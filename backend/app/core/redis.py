import asyncio
from typing import Any
from weakref import WeakKeyDictionary

from redis.asyncio import Redis

from app.core.config import get_settings


def _client() -> Redis:
    return Redis.from_url(
        get_settings().redis_url,
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
    )


class _PerLoopRedis:
    """Serverless runtimes may give each request its own event loop, and a Redis connection only
    works on the loop that opened it. ponytail: a dead loop's sockets close at GC, not gracefully."""

    def __init__(self) -> None:
        self._clients: WeakKeyDictionary[asyncio.AbstractEventLoop, Redis] = WeakKeyDictionary()

    def __getattr__(self, name: str) -> Any:
        loop = asyncio.get_running_loop()
        if loop not in self._clients:
            self._clients[loop] = _client()
        return getattr(self._clients[loop], name)


redis: Any = _PerLoopRedis() if get_settings().db_null_pool else _client()

WORKER_HEARTBEAT_KEY = "worker:heartbeat"
