import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import DB
from app.payments import service as payments
from app.payments.provider import PaymentProvider, get_payment_provider
from app.shipping import service as shipping
from app.shipping.provider import ShippingProvider, get_shipping_provider
from app.webhooks.service import process

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
MAX_BODY = 512 * 1024


def _rejected(reason: str) -> JSONResponse:
    return JSONResponse(
        {"success": False, "error": {"code": "WEBHOOK_REJECTED", "message": reason}}, status_code=400
    )


async def _body(request: Request) -> bytes | None:
    body = await request.body()
    return body if len(body) <= MAX_BODY else None


@router.post("/razorpay", include_in_schema=False)
async def razorpay(
    request: Request, db: DB, provider: Annotated[PaymentProvider, Depends(get_payment_provider)]
):
    body = await _body(request)
    # Signature over the *raw* bytes: never re-serialise before verifying.
    if body is None or not provider.verify_webhook(body, request.headers.get("x-razorpay-signature", "")):
        return _rejected("invalid signature")
    event = provider.parse_webhook(body)
    event_id = request.headers.get("x-razorpay-event-id") or hashlib.sha256(body).hexdigest()

    async def handle(session) -> bool:
        if event.type in ("payment.captured", "payment.authorized", "payment.failed") and event.payment:
            return await payments.apply_payment(session, provider, event.payment)
        if event.type in ("refund.processed", "refund.failed") and event.refund:
            return await payments.on_refund_update(session, event.refund)
        return False  # verified but not interesting: stored as IGNORED

    status = await process(db, "razorpay", event_id, event.type, body, handle)
    return {"success": True, "status": status}


@router.post("/shipping", include_in_schema=False)
async def shipping_webhook(
    request: Request, db: DB, provider: Annotated[ShippingProvider, Depends(get_shipping_provider)]
):
    body = await _body(request)
    if body is None or not provider.verify_webhook({k.lower(): v for k, v in request.headers.items()}):
        return _rejected("invalid token")
    try:
        payload = json.loads(body)
    except ValueError:
        return _rejected("invalid json")
    # Tracking pushes have no event id; identical payloads are identical events.
    event_id = hashlib.sha256(body).hexdigest()
    status = await process(
        db,
        provider.name,
        event_id,
        str(payload.get("current_status", "tracking"))[:64],
        body,
        lambda session: shipping.handle_webhook(session, provider, payload),
    )
    return {"success": True, "status": status}
