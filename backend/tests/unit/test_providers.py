import base64
import hashlib
import hmac
import json

import httpx
import pytest

from app.core.redis import redis
from app.payments.provider import PaymentProviderError, RazorpayProvider
from app.shipping.provider import ShipmentStatus, ShiprocketProvider


def rzp(handler) -> RazorpayProvider:
    return RazorpayProvider("rzp_key", "secret", "whsec", transport=httpx.MockTransport(handler))


async def test_razorpay_create_order_uses_basic_auth_and_paise():
    seen = {}

    def handler(request: httpx.Request):
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "order_1", "amount": 24900, "currency": "INR"})

    order = await rzp(handler).create_order(24900, "INR", "HSC-ABC", {"order_id": "x"})
    assert order.id == "order_1"
    assert seen["auth"] == "Basic " + base64.b64encode(b"rzp_key:secret").decode()
    assert seen["body"]["amount"] == 24900 and seen["body"]["receipt"] == "HSC-ABC"


@pytest.mark.parametrize(("status", "ambiguous"), [(400, False), (502, True)])
async def test_razorpay_errors_classified(status, ambiguous):
    with pytest.raises(PaymentProviderError) as e:
        await rzp(lambda r: httpx.Response(status, json={})).refund("pay_1", 100, {})
    assert e.value.ambiguous is ambiguous


async def test_razorpay_network_failure_is_ambiguous():
    def boom(request):
        raise httpx.ConnectTimeout("timeout")

    with pytest.raises(PaymentProviderError) as e:
        await rzp(boom).refund("pay_1", 100, {})
    assert e.value.ambiguous is True


def test_razorpay_signatures():
    p = rzp(lambda r: httpx.Response(200))
    good = hmac.new(b"secret", b"order_1|pay_1", hashlib.sha256).hexdigest()
    assert p.verify_checkout_signature("order_1", "pay_1", good)
    assert not p.verify_checkout_signature("order_1", "pay_2", good)  # signature bound to this payment
    body = b'{"event":"order.paid"}'
    assert p.verify_webhook(body, hmac.new(b"whsec", body, hashlib.sha256).hexdigest())
    assert not p.verify_webhook(body + b" ", hmac.new(b"whsec", body, hashlib.sha256).hexdigest())


def test_razorpay_order_paid_maps_to_captured():
    body = json.dumps(
        {
            "event": "order.paid",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_1",
                        "order_id": "order_1",
                        "status": "captured",
                        "amount": 500,
                        "method": "upi",
                    }
                }
            },
        }
    ).encode()
    event = rzp(lambda r: httpx.Response(200)).parse_webhook(body)
    assert event.type == "payment.captured" and event.payment.amount_paise == 500


async def test_shiprocket_caches_token_and_relogs_on_401():
    await redis.delete(ShiprocketProvider.TOKEN_KEY)
    calls = {"login": 0, "track": 0}

    def handler(request: httpx.Request):
        if request.url.path.endswith("/auth/login"):
            calls["login"] += 1
            return httpx.Response(200, json={"token": f"tok{calls['login']}"})
        calls["track"] += 1
        if request.headers["authorization"] == "Bearer tok1" and calls["track"] == 2:
            return httpx.Response(401)  # token revoked server-side
        return httpx.Response(
            200,
            json={
                "tracking_data": {
                    "shipment_track": [{"current_status": "OUT FOR DELIVERY"}],
                    "shipment_track_activities": [
                        {"date": "2026-10-07 09:00:00", "activity": "Out for delivery"}
                    ],
                }
            },
        )

    p = ShiprocketProvider("e", "p", "Primary", "110001", "tok", transport=httpx.MockTransport(handler))
    first = await p.track("AWB1")
    assert (
        first.status == ShipmentStatus.OUT_FOR_DELIVERY
        and first.events[0].occurred_at.utcoffset().seconds == 19800
    )
    await p.track("AWB1")  # 401 -> one re-login -> success
    await p.track("AWB1")  # cached new token
    assert calls["login"] == 2
    await redis.delete(ShiprocketProvider.TOKEN_KEY)


def test_shiprocket_webhook_token():
    p = ShiprocketProvider("e", "p", "Primary", "110001", "secret-token")
    assert p.verify_webhook({"x-api-key": "secret-token"})
    assert not p.verify_webhook({"x-api-key": "secret-tokem"})
    assert not ShiprocketProvider("e", "p", "Primary", "110001", None).verify_webhook({"x-api-key": ""})
