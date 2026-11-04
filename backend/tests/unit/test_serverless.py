import asyncio

from app.core.redis import _PerLoopRedis


def test_each_event_loop_gets_its_own_redis_client():
    redis = _PerLoopRedis()

    async def client_id() -> int:
        return id(redis.connection_pool)

    async def same_loop_twice() -> bool:
        return await client_id() == await client_id()

    first, second = asyncio.new_event_loop(), asyncio.new_event_loop()
    assert first.run_until_complete(same_loop_twice())
    assert first.run_until_complete(client_id()) != second.run_until_complete(client_id())
    first.close()
    second.close()
