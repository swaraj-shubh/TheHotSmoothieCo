"""Payment gateway abstraction. Business logic only sees these dataclasses; adding Cashfree/Stripe
means one new class implementing PaymentProvider."""

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from typing import Protocol

import httpx
import structlog

from app.core.config import get_settings
from app.core.exceptions import AppError

log = structlog.get_logger()


class PaymentProviderUnavailable(AppError):
    status_code, code, message = 503, "PAYMENTS_UNAVAILABLE", "Payments are temporarily unavailable"


class PaymentProviderError(AppError):
    status_code, code, message = (
        502,
        "PAYMENT_PROVIDER_ERROR",
        "The payment provider could not process this request",
    )

    def __init__(self, *, ambiguous: bool):
        # ambiguous=True: timeout / 5xx — the gateway may or may not have acted.
        super().__init__()
        self.ambiguous = ambiguous


@dataclass(frozen=True)
class ProviderOrder:
    id: str
    amount_paise: int
    currency: str


@dataclass(frozen=True)
class ProviderPayment:
    id: str
    order_id: str
    status: str  # normalised: "captured" | "authorized" | "failed" | "created"
    amount_paise: int
    method: str | None = None
    error_code: str | None = None
    error_description: str | None = None


@dataclass(frozen=True)
class ProviderRefund:
    id: str
    payment_id: str
    status: str  # "pending" | "processed" | "failed"
    amount_paise: int
    notes: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderEvent:
    """A verified webhook, normalised."""

    type: str  # "payment.captured" | "payment.failed" | "refund.processed" | "refund.failed" | other
    payment: ProviderPayment | None = None
    refund: ProviderRefund | None = None


class PaymentProvider(Protocol):
    name: str
    public_key: str

    async def create_order(
        self, amount_paise: int, currency: str, receipt: str, notes: dict
    ) -> ProviderOrder: ...
    async def fetch_payment(self, payment_id: str) -> ProviderPayment: ...
    async def refund(self, payment_id: str, amount_paise: int, notes: dict) -> ProviderRefund: ...
    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool: ...
    def verify_webhook(self, body: bytes, signature: str) -> bool: ...
    def parse_webhook(self, body: bytes) -> ProviderEvent: ...


def _hmac_ok(secret: str, message: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")  # constant time


class RazorpayProvider:
    name = "razorpay"
    BASE = "https://api.razorpay.com/v1"

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        webhook_secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.public_key = key_id
        self._secret = key_secret
        self._webhook_secret = webhook_secret
        self._transport = transport

    async def _call(self, method: str, path: str, payload: dict | None = None) -> dict:
        try:
            async with httpx.AsyncClient(
                base_url=self.BASE,
                auth=(self.public_key, self._secret),
                timeout=15,
                transport=self._transport,
            ) as client:
                r = await client.request(method, path, json=payload)
        except httpx.HTTPError as exc:
            log.error("razorpay_unreachable", path=path, error=str(exc))
            raise PaymentProviderError(ambiguous=True) from exc
        if r.status_code >= 400:
            # Body may describe the problem; it never contains our secret.
            log.error("razorpay_error", path=path, status=r.status_code, body=r.text[:500])
            raise PaymentProviderError(ambiguous=r.status_code >= 500)
        return r.json()

    @staticmethod
    def _payment(e: dict) -> ProviderPayment:
        status = {"captured": "captured", "authorized": "authorized", "failed": "failed"}.get(
            e.get("status") or "", "created"
        )
        return ProviderPayment(
            id=e["id"],
            order_id=e.get("order_id") or "",
            status=status,
            amount_paise=e["amount"],
            method=e.get("method"),
            error_code=e.get("error_code"),
            error_description=e.get("error_description"),
        )

    @staticmethod
    def _refund(e: dict) -> ProviderRefund:
        return ProviderRefund(
            id=e["id"],
            payment_id=e["payment_id"],
            status=e.get("status", "pending"),
            amount_paise=e["amount"],
            notes=e.get("notes") or {},
        )

    async def create_order(
        self, amount_paise: int, currency: str, receipt: str, notes: dict
    ) -> ProviderOrder:
        body = await self._call(
            "POST",
            "/orders",
            {
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt,
                "notes": notes,
                "payment_capture": 1,
            },
        )
        return ProviderOrder(id=body["id"], amount_paise=body["amount"], currency=body["currency"])

    async def fetch_payment(self, payment_id: str) -> ProviderPayment:
        return self._payment(await self._call("GET", f"/payments/{payment_id}"))

    async def refund(self, payment_id: str, amount_paise: int, notes: dict) -> ProviderRefund:
        return self._refund(
            await self._call(
                "POST", f"/payments/{payment_id}/refund", {"amount": amount_paise, "notes": notes}
            )
        )

    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        return _hmac_ok(self._secret, f"{order_id}|{payment_id}".encode(), signature)

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        return _hmac_ok(self._webhook_secret, body, signature)

    def parse_webhook(self, body: bytes) -> ProviderEvent:
        data = json.loads(body)
        event, payload = data.get("event", ""), data.get("payload", {})
        payment = payload.get("payment", {}).get("entity")
        refund = payload.get("refund", {}).get("entity")
        type_ = "payment.captured" if event == "order.paid" else event
        return ProviderEvent(
            type=type_,
            payment=self._payment(payment) if payment else None,
            refund=self._refund(refund) if refund else None,
        )


class DevPaymentProvider:
    """Simulated gateway for local development and E2E tests: no network, no credentials.
    Stateless (ids encode what they need), so it works across several API instances. Payments are
    "made" via POST /payments/orders/{id}/simulate, which runs the same capture handler as a real
    webhook. Refused in production by config validation."""

    name = "dev"
    public_key = "dev"

    async def create_order(
        self, amount_paise: int, currency: str, receipt: str, notes: dict
    ) -> ProviderOrder:
        return ProviderOrder(f"devorder_{receipt}_{amount_paise}", amount_paise, currency)

    def payment_for(self, order_id: str, success: bool) -> ProviderPayment:
        amount = int(order_id.rsplit("_", 1)[1])
        status = "captured" if success else "failed"
        return ProviderPayment(
            id=f"devpay_{status}_{order_id}",
            order_id=order_id,
            status=status,
            amount_paise=amount,
            method="dev",
            error_code=None if success else "DEV_DECLINED",
            error_description=None if success else "Simulated decline",
        )

    async def fetch_payment(self, payment_id: str) -> ProviderPayment:
        _, status, order_id = payment_id.split("_", 2)
        return self.payment_for(order_id, status == "captured")

    async def refund(self, payment_id: str, amount_paise: int, notes: dict) -> ProviderRefund:
        return ProviderRefund(
            f"devrefund_{notes.get('refund_id', payment_id)}", payment_id, "processed", amount_paise, notes
        )

    def verify_checkout_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        return False  # the dev flow uses /simulate, never client signatures

    def verify_webhook(self, body: bytes, signature: str) -> bool:
        return False

    def parse_webhook(self, body: bytes) -> ProviderEvent:
        raise NotImplementedError


def get_payment_provider() -> PaymentProvider:
    s = get_settings()
    if s.payments_provider == "dev":
        return DevPaymentProvider()
    if not (s.razorpay_key_id and s.razorpay_key_secret and s.razorpay_webhook_secret):
        raise PaymentProviderUnavailable()
    return RazorpayProvider(
        s.razorpay_key_id,
        s.razorpay_key_secret.get_secret_value(),
        s.razorpay_webhook_secret.get_secret_value(),
    )


def optional_payment_provider() -> PaymentProvider | None:
    """For endpoints that only *sometimes* need the gateway (e.g. cancelling an unpaid order)."""
    try:
        return get_payment_provider()
    except PaymentProviderUnavailable:
        return None
