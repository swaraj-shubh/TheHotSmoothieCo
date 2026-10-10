from redis.asyncio import Redis

from app.core.config import get_settings

redis = Redis.from_url(
    get_settings().redis_url,
    decode_responses=True,
    socket_timeout=2,
    socket_connect_timeout=2,
    health_check_interval=30,
)

WORKER_HEARTBEAT_KEY = "worker:heartbeat"
