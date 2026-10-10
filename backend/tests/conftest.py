import os
import subprocess
import sys

# Must be set before any app module creates the engine / redis client.
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres@127.0.0.1:5432/hsc_test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.redis import redis  # noqa: E402
from app.main import app  # noqa: E402

# Reference data seeded by migrations; never truncated.
KEEP = {"roles", "alembic_version"}


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    """Tests run against the real migrations, so a broken migration fails CI."""
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=os.environ)


@pytest.fixture(autouse=True)
async def clean_state():
    yield
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables if t.name not in KEEP)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    await redis.flushdb()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def db():
    async with SessionLocal() as session:
        yield session


# ---------- shared helpers ----------

PASSWORD = "correct-horse-battery"


async def signup(client, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PASSWORD, "full_name": "T"}
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def customer(client) -> dict:
    return await signup(client, "customer@example.com")


@pytest.fixture
def staff(client, db):
    """`headers = await staff("PRODUCT_MANAGER")` -> auth headers for a user with that role."""
    from app.users import repository

    async def make(*roles: str) -> dict:
        email = f"{'-'.join(roles).lower() or 'norole'}@staff.example.com"
        headers = await signup(client, email)
        user = await repository.get_by_email(db, email)
        user.roles = await repository.get_roles(db, list(roles))
        await db.commit()
        return headers

    return make


class FakeStorage:
    provider = "fake"

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.deleted: list[str] = []

    async def upload(self, data: bytes, folder: str):
        from app.media.storage import StoredMedia

        key = f"{folder}/{len(self.files)}"
        self.files[key] = data
        return StoredMedia(
            "fake",
            key,
            f"https://cdn.test/{key}",
            f"https://cdn.test/thumb/{key}",
            100,
            100,
            "png",
            len(data),
        )

    async def delete(self, key: str) -> None:
        self.deleted.append(key)

    def url_for(self, key: str, *, width: int, height: int | None = None) -> str:
        return f"https://cdn.test/{width}/{key}"


@pytest.fixture
def storage():
    from app.media.storage import get_media_storage

    fake = FakeStorage()
    app.dependency_overrides[get_media_storage] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_media_storage, None)


@pytest.fixture
def make_user():
    """`user, headers = await make_user("a@x.com")` — created directly (bypasses register rate limits)."""
    from app.auth import service as auth
    from app.core.security import hash_password
    from app.users.models import User

    async def make(email: str):
        async with SessionLocal() as s:
            s.add(
                User(
                    email=email,
                    full_name=email.split("@")[0],
                    password_hash=hash_password(PASSWORD),
                    roles=[],
                )
            )
            await s.commit()
            user, tokens = await auth.login(s, email, PASSWORD, None, None)
            return user, {"Authorization": f"Bearer {tokens.access_token}"}

    return make


# ---------- fake gateways (real signature/parsing code, no network) ----------

RZP_SECRET, RZP_WEBHOOK_SECRET, SHIP_TOKEN = "test_key_secret", "test_webhook_secret", "test-ship-token"


class FakeRazorpay:
    """Subclasses the real provider so signature checks and webhook parsing are production code."""

    def __new__(cls):
        from app.payments.provider import (
            PaymentProviderError,
            ProviderOrder,
            ProviderPayment,
            ProviderRefund,
            RazorpayProvider,
        )

        class _Fake(RazorpayProvider):
            def __init__(self):
                super().__init__("rzp_test_key", RZP_SECRET, RZP_WEBHOOK_SECRET)
                self.orders: dict[str, int] = {}
                self.payments: dict[str, ProviderPayment] = {}
                self.refunds: list[ProviderRefund] = []
                self.refund_mode = "processed"  # | "pending" | "ambiguous" | "rejected"
                self._n = 0

            def _id(self, prefix):
                self._n += 1
                return f"{prefix}_{self._n:06d}"

            async def create_order(self, amount_paise, currency, receipt, notes):
                oid = self._id("order")
                self.orders[oid] = amount_paise
                return ProviderOrder(oid, amount_paise, currency)

            def pay(self, order_id, status="captured", amount=None, method="upi"):
                p = ProviderPayment(
                    self._id("pay"),
                    order_id,
                    status,
                    amount or self.orders[order_id],
                    method,
                    "BAD_REQUEST_ERROR" if status == "failed" else None,
                    "Card declined" if status == "failed" else None,
                )
                self.payments[p.id] = p
                return p

            async def fetch_payment(self, payment_id):
                return self.payments[payment_id]

            async def refund(self, payment_id, amount_paise, notes):
                if self.refund_mode == "ambiguous":
                    raise PaymentProviderError(ambiguous=True)
                if self.refund_mode == "rejected":
                    raise PaymentProviderError(ambiguous=False)
                r = ProviderRefund(self._id("rfnd"), payment_id, self.refund_mode, amount_paise, notes)
                self.refunds.append(r)
                return r

        return _Fake()


class FakeShiprocket:
    def __new__(cls):
        from app.shipping.provider import (
            Awb,
            CreatedShipment,
            Rate,
            ShippingProviderError,
            ShiprocketProvider,
        )

        class _Fake(ShiprocketProvider):
            def __init__(self):
                super().__init__("ops@x.com", "pw", "Primary", "110001", SHIP_TOKEN)
                self.created: list[tuple[dict, object, bool]] = []
                self.cancelled: list[str] = []
                self.fail_awb = False
                self.tracking: dict = {}
                self._n = 0

            async def rates(self, delivery_pincode, weight_grams):
                return (
                    []
                    if delivery_pincode.startswith("9")
                    else [Rate("Delhivery", 6500, 4), Rate("Bluedart", 9000, 2)]
                )

            async def create_shipment(self, order, package, *, is_return=False):
                self._n += 1
                self.created.append((order, package, is_return))
                return CreatedShipment(f"SRO{self._n}", f"SRS{self._n}")

            async def assign_awb(self, provider_shipment_id):
                if self.fail_awb:
                    raise ShippingProviderError()
                return Awb(f"AWB{provider_shipment_id}", "Delhivery")

            async def label(self, provider_shipment_id):
                return f"https://labels.test/{provider_shipment_id}.pdf"

            async def track(self, awb):
                return self.tracking[awb]

            async def cancel(self, provider_order_id):
                self.cancelled.append(provider_order_id)

        return _Fake()


@pytest.fixture
def pay():
    from app.payments.provider import get_payment_provider, optional_payment_provider

    fake = FakeRazorpay()
    app.dependency_overrides[get_payment_provider] = lambda: fake
    app.dependency_overrides[optional_payment_provider] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_payment_provider, None)
    app.dependency_overrides.pop(optional_payment_provider, None)


@pytest.fixture
def ship():
    from app.shipping.provider import get_shipping_provider, optional_shipping_provider

    fake = FakeShiprocket()
    app.dependency_overrides[get_shipping_provider] = lambda: fake
    app.dependency_overrides[optional_shipping_provider] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_shipping_provider, None)
    app.dependency_overrides.pop(optional_shipping_provider, None)


class Outbox:
    """Reads the notification outbox (what the worker would send)."""

    async def rows(self, template: str | None = None) -> list:
        from sqlalchemy import select

        from app.notifications.models import Notification

        async with SessionLocal() as s:
            stmt = select(Notification).order_by(Notification.created_at)
            if template:
                stmt = stmt.where(Notification.template == template)
            return list(await s.scalars(stmt))

    async def count(self, template: str | None = None) -> int:
        return len(await self.rows(template))

    async def token(self, template: str) -> str:
        import re

        link = (await self.rows(template))[-1].context["link"]
        return re.search(r"token=([\w-]+)", link).group(1)


@pytest.fixture
def outbox() -> Outbox:
    return Outbox()
