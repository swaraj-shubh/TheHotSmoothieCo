"""Background worker: `python -m app.workers`.

All durable work lives in Postgres (outbox rows, order/payment/shipment state), so the worker is
just a scheduler. Postgres advisory locks ensure each job runs on one worker at a time across any
number of worker containers, and a dead worker's lock is released with its connection.
A failing job is logged/reported and retried next tick; it never takes the worker down.
"""

import asyncio
import hashlib
import signal
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import sentry_sdk
import structlog
from redis.exceptions import RedisError
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.database import engine
from app.core.logging import configure_logging
from app.core.redis import WORKER_HEARTBEAT_KEY, redis
from app.workers import jobs

log = structlog.get_logger("worker")


@dataclass(frozen=True)
class Job:
    name: str
    every_seconds: int
    fn: Callable[[], Awaitable[int]]

    @property
    def lock_key(self) -> int:
        return int.from_bytes(
            hashlib.sha256(f"hsc-job:{self.name}".encode()).digest()[:8], "big", signed=True
        )


JOBS = [
    Job("drain_notifications", 5, jobs.drain_notifications),
    Job("expire_unpaid_orders", 60, jobs.expire_unpaid_orders),
    Job("reconcile_payments", 15 * 60, jobs.reconcile_payments),
    Job("sync_shipments", 30 * 60, jobs.sync_shipments),
    Job("abandoned_carts", 60 * 60, jobs.abandoned_carts),
    Job("reindex_search", 6 * 60 * 60, jobs.reindex_search),
    Job("cleanup", 24 * 60 * 60, jobs.cleanup),
]


async def run_job(job: Job) -> bool:
    """Run `job` unless another worker holds its lock. Returns whether it ran."""
    async with engine.connect() as conn:
        if not await conn.scalar(select(func.pg_try_advisory_lock(job.lock_key))):
            return False
        started = time.perf_counter()
        try:
            result = await job.fn()
            if result:
                log.info(
                    "job_done", job=job.name, result=result, ms=round((time.perf_counter() - started) * 1000)
                )
        except Exception as exc:
            log.exception("job_failed", job=job.name, exc_info=exc)
            sentry_sdk.capture_exception(exc)
        finally:
            try:
                await conn.scalar(select(func.pg_advisory_unlock(job.lock_key)))
            except Exception:
                await conn.invalidate()  # never return a connection that may still hold the lock
    return True


async def _heartbeat() -> None:
    try:
        await redis.set(WORKER_HEARTBEAT_KEY, int(time.time()), ex=60)
    except RedisError:
        pass  # monitoring only; jobs don't depend on Redis


async def run_loop(stop: asyncio.Event) -> None:
    """The scheduler. Used by the standalone worker and, optionally, inside the API process."""
    next_run = dict.fromkeys((j.name for j in JOBS), 0.0)
    running: dict[str, asyncio.Task] = {}
    log.info("worker_started", jobs=[j.name for j in JOBS])
    while not stop.is_set():
        now = time.monotonic()
        for job in JOBS:
            busy = job.name in running and not running[job.name].done()
            if now >= next_run[job.name] and not busy:
                next_run[job.name] = now + job.every_seconds
                running[job.name] = asyncio.create_task(run_job(job))
        await _heartbeat()
        try:
            await asyncio.wait_for(stop.wait(), timeout=1)
        except TimeoutError:
            pass

    log.info("worker_stopping")
    pending = [t for t in running.values() if not t.done()]
    if pending:
        await asyncio.wait(pending, timeout=25)  # let in-flight jobs finish their current batch


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.debug)
    if settings.sentry_dsn:
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.environment, send_default_pii=False)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    await run_loop(stop)
    await redis.aclose()
    await engine.dispose()
