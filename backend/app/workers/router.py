import hmac
from typing import Annotated

from fastapi import APIRouter, Header

from app.core.config import get_settings
from app.core.exceptions import NotFound
from app.workers.runner import run_due

router = APIRouter(include_in_schema=False)


@router.get("/internal/cron")
async def cron(authorization: Annotated[str | None, Header()] = None):
    """Runs due background jobs. For hosts without a worker process; disabled unless CRON_SECRET is set."""
    secret = get_settings().cron_secret
    expected = f"Bearer {secret.get_secret_value()}" if secret else ""
    if not secret or not hmac.compare_digest((authorization or "").encode(), expected.encode()):
        raise NotFound()  # don't advertise the endpoint
    return {"ran": await run_due()}
