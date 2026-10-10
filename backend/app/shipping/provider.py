"""Shipping aggregator abstraction + Shiprocket implementation.

ponytail: Shiprocket request/response shapes follow their public API docs; verify each call
against a sandbox account once credentials exist (tests cover our logic via a fake provider).
"""

import enum
import hmac
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
import structlog
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.redis import redis

log = structlog.get_logger()


class ShippingUnavailable(AppError):
    status_code, code, message = 503, "SHIPPING_UNAVAILABLE", "Shipping service is temporarily unavailable"


class ShippingProviderError(AppError):
    status_code, code, message = (
        502,
        "SHIPPING_PROVIDER_ERROR",
        "The shipping provider could not process this request",
    )


class ShipmentStatus(enum.StrEnum):
    CREATED = "CREATED"
    AWB_ASSIGNED = "AWB_ASSIGNED"
    PICKUP_SCHEDULED = "PICKUP_SCHEDULED"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RTO = "RTO"  # undeliverable, returning to us
    EXCEPTION = "EXCEPTION"


ACTIVE_SHIPMENT_STATUSES = {
    ShipmentStatus.CREATED,
    ShipmentStatus.AWB_ASSIGNED,
    ShipmentStatus.PICKUP_SCHEDULED,
    ShipmentStatus.IN_TRANSIT,
    ShipmentStatus.OUT_FOR_DELIVERY,
    ShipmentStatus.EXCEPTION,
}


@dataclass(frozen=True)
class Package:
    weight_grams: int
    length_cm: int
    breadth_cm: int
    height_cm: int


@dataclass(frozen=True)
class Rate:
    courier: str
    rate_paise: int
    estimated_days: int | None


@dataclass(frozen=True)
class CreatedShipment:
    provider_order_id: str
    provider_shipment_id: str


@dataclass(frozen=True)
class Awb:
    awb: str
    courier: str


@dataclass(frozen=True)
class TrackingEvent:
    status: ShipmentStatus
    raw_status: str
    occurred_at: datetime
    location: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class TrackingUpdate:
    awb: str
    status: ShipmentStatus
    raw_status: str
    events: list[TrackingEvent] = field(default_factory=list)


class ShippingProvider(Protocol):
    name: str

    async def rates(self, delivery_pincode: str, weight_grams: int) -> list[Rate]: ...
    async def create_shipment(
        self, order: dict, package: Package, *, is_return: bool = False
    ) -> CreatedShipment: ...
    async def assign_awb(self, provider_shipment_id: str) -> Awb: ...
    async def label(self, provider_shipment_id: str) -> str | None: ...
    async def track(self, awb: str) -> TrackingUpdate: ...
    async def cancel(self, provider_order_id: str) -> None: ...
    def verify_webhook(self, headers: dict[str, str]) -> bool: ...
    def parse_webhook(self, payload: dict) -> TrackingUpdate: ...


# Courier wording varies wildly; match on keywords, most specific first.
_STATUS_KEYWORDS = [
    ("RTO", ShipmentStatus.RTO),
    ("UNDELIVERED", ShipmentStatus.EXCEPTION),
    ("OUT FOR DELIVERY", ShipmentStatus.OUT_FOR_DELIVERY),
    ("DELIVERED", ShipmentStatus.DELIVERED),
    ("CANCEL", ShipmentStatus.CANCELLED),
    ("PICKUP SCHEDULED", ShipmentStatus.PICKUP_SCHEDULED),
    ("PICKUP GENERATED", ShipmentStatus.PICKUP_SCHEDULED),
    ("OUT FOR PICKUP", ShipmentStatus.PICKUP_SCHEDULED),
    ("PICKED UP", ShipmentStatus.IN_TRANSIT),
    ("SHIPPED", ShipmentStatus.IN_TRANSIT),
    ("TRANSIT", ShipmentStatus.IN_TRANSIT),
    ("REACHED", ShipmentStatus.IN_TRANSIT),
    ("LOST", ShipmentStatus.EXCEPTION),
    ("DAMAGED", ShipmentStatus.EXCEPTION),
    ("AWB ASSIGNED", ShipmentStatus.AWB_ASSIGNED),
]


def normalise_status(raw: str) -> ShipmentStatus:
    upper = (raw or "").upper()
    for keyword, status in _STATUS_KEYWORDS:
        if keyword in upper:
            return status
    return ShipmentStatus.IN_TRANSIT if upper else ShipmentStatus.CREATED


IST = ZoneInfo("Asia/Kolkata")


def _parse_time(value: str | None) -> datetime:
    """Shiprocket timestamps are IST without an offset."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d %m %Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime((value or "")[:19], fmt).replace(tzinfo=IST)
        except ValueError:
            continue
    return datetime.now(IST)


class ShiprocketProvider:
    name = "shiprocket"
    BASE = "https://apiv2.shiprocket.in/v1/external"
    TOKEN_KEY = "shiprocket:token"  # noqa: S105 (redis key name)

    def __init__(
        self,
        email: str,
        password: str,
        pickup_location: str,
        pickup_pincode: str,
        webhook_token: str | None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._email, self._password = email, password
        self._pickup_location, self._pickup_pincode = pickup_location, pickup_pincode
        self._webhook_token = webhook_token
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.BASE, timeout=20, transport=self._transport)

    async def _token(self, refresh: bool = False) -> str:
        # Tokens last ~10 days; share one across all API instances via Redis.
        if not refresh:
            try:
                if cached := await redis.get(self.TOKEN_KEY):
                    return str(cached)
            except RedisError:
                pass
        async with self._client() as c:
            r = await c.post("/auth/login", json={"email": self._email, "password": self._password})
        if r.status_code != 200:
            log.error("shiprocket_auth_failed", status=r.status_code)
            raise ShippingProviderError()
        token = r.json()["token"]
        try:
            await redis.set(self.TOKEN_KEY, token, ex=8 * 24 * 3600)
        except RedisError:
            pass
        return token

    async def _call(self, method: str, path: str, **kwargs) -> dict:
        for attempt in (0, 1):
            token = await self._token(refresh=attempt == 1)
            try:
                async with self._client() as c:
                    r = await c.request(method, path, headers={"Authorization": f"Bearer {token}"}, **kwargs)
            except httpx.HTTPError as exc:
                log.error("shiprocket_unreachable", path=path, error=str(exc))
                raise ShippingProviderError() from exc
            if r.status_code == 401 and attempt == 0:
                continue  # token expired early: re-login once
            if r.status_code >= 400:
                log.error("shiprocket_error", path=path, status=r.status_code, body=r.text[:500])
                raise ShippingProviderError()
            return r.json()
        raise ShippingProviderError()

    async def rates(self, delivery_pincode: str, weight_grams: int) -> list[Rate]:
        body = await self._call(
            "GET",
            "/courier/serviceability/",
            params={
                "pickup_postcode": self._pickup_pincode,
                "delivery_postcode": delivery_pincode,
                "weight": max(weight_grams, 1) / 1000,
                "cod": 0,
            },
        )
        couriers = (body.get("data") or {}).get("available_courier_companies") or []
        return [
            Rate(
                c.get("courier_name", "?"),
                round(float(c.get("rate", 0)) * 100),
                int(c["estimated_delivery_days"])
                if str(c.get("estimated_delivery_days", "")).isdigit()
                else None,
            )
            for c in couriers
        ]

    async def create_shipment(
        self, order: dict, package: Package, *, is_return: bool = False
    ) -> CreatedShipment:
        a = order["shipping_address"]
        payload = {
            "order_id": order["number"] + ("-R" if is_return else ""),
            "order_date": order["created_at"][:16].replace("T", " "),
            "pickup_location": self._pickup_location,
            "billing_customer_name": a["full_name"],
            "billing_last_name": "",
            "billing_address": a["line1"],
            "billing_address_2": a.get("line2") or "",
            "billing_city": a["city"],
            "billing_pincode": a["postal_code"],
            "billing_state": a["state"],
            "billing_country": "India",
            "billing_email": order["customer_email"],
            "billing_phone": a["phone"],
            "shipping_is_billing": True,
            "order_items": [
                {
                    "name": f"{i['product_title']} ({i['variant_title']})",
                    "sku": i["sku"],
                    "units": i["quantity"],
                    "selling_price": i["unit_price_paise"] / 100,
                }
                for i in order["items"]
            ],
            "payment_method": "Prepaid",
            "sub_total": order["total_paise"] / 100,
            "length": package.length_cm,
            "breadth": package.breadth_cm,
            "height": package.height_cm,
            "weight": package.weight_grams / 1000,
        }
        path = "/orders/create/return" if is_return else "/orders/create/adhoc"
        body = await self._call("POST", path, json=payload)
        return CreatedShipment(str(body["order_id"]), str(body["shipment_id"]))

    async def assign_awb(self, provider_shipment_id: str) -> Awb:
        body = await self._call("POST", "/courier/assign/awb", json={"shipment_id": provider_shipment_id})
        data = (body.get("response") or {}).get("data") or {}
        if not data.get("awb_code"):
            raise ShippingProviderError("No courier could be assigned to this shipment")
        return Awb(data["awb_code"], data.get("courier_name") or "")

    async def label(self, provider_shipment_id: str) -> str | None:
        body = await self._call(
            "POST", "/courier/generate/label", json={"shipment_id": [provider_shipment_id]}
        )
        return body.get("label_url")

    async def track(self, awb: str) -> TrackingUpdate:
        body = await self._call("GET", f"/courier/track/awb/{awb}")
        data = body.get("tracking_data") or {}
        raw = ((data.get("shipment_track") or [{}])[0]).get("current_status") or ""
        events = [
            TrackingEvent(
                normalise_status(e.get("activity") or e.get("status") or ""),
                e.get("activity") or "",
                _parse_time(e.get("date")),
                e.get("location"),
            )
            for e in data.get("shipment_track_activities") or []
        ]
        return TrackingUpdate(awb, normalise_status(raw), raw, events)

    async def cancel(self, provider_order_id: str) -> None:
        await self._call("POST", "/orders/cancel", json={"ids": [provider_order_id]})

    def verify_webhook(self, headers: dict[str, str]) -> bool:
        sent = headers.get("x-api-key", "")
        return bool(self._webhook_token) and hmac.compare_digest(sent, self._webhook_token or "")

    def parse_webhook(self, payload: dict) -> TrackingUpdate:
        raw = payload.get("current_status") or payload.get("shipment_status") or ""
        events = [
            TrackingEvent(
                normalise_status(s.get("status") or s.get("activity") or ""),
                s.get("activity") or s.get("status") or "",
                _parse_time(s.get("date")),
                s.get("location"),
            )
            for s in payload.get("scans") or []
        ]
        return TrackingUpdate(str(payload.get("awb", "")), normalise_status(raw), raw, events)


def get_shipping_provider() -> ShippingProvider:
    s = get_settings()
    if not (s.shiprocket_email and s.shiprocket_password):
        raise ShippingUnavailable()
    return ShiprocketProvider(
        s.shiprocket_email,
        s.shiprocket_password.get_secret_value(),
        s.shiprocket_pickup_location,
        s.warehouse_pincode,
        s.shipping_webhook_token.get_secret_value() if s.shipping_webhook_token else None,
    )


def optional_shipping_provider() -> ShippingProvider | None:
    try:
        return get_shipping_provider()
    except ShippingUnavailable:
        return None
