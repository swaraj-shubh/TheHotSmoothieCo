from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    """All configuration comes from environment variables (or .env in development)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TheHotSmoothieCo"
    environment: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://postgres@127.0.0.1:5432/hsc"
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # True when DATABASE_URL points at a transaction-mode pooler (Supabase :6543, Neon "-pooler" host,
    # RDS Proxy...). asyncpg's prepared-statement cache breaks under transaction pooling.
    db_pgbouncer: bool = False
    redis_url: str = "redis://127.0.0.1:6379/0"

    jwt_secret: SecretStr = SecretStr("dev-only-change-me-dev-only-change-me")
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 15 * 60
    refresh_token_ttl_seconds: int = 30 * 24 * 3600
    email_token_ttl_seconds: int = 24 * 3600
    password_reset_ttl_seconds: int = 3600

    rate_limit_enabled: bool = True  # only for load tests; refused in production
    run_worker_in_api: bool = False  # run background jobs inside the API process (no separate worker)

    # How to find the real client IP behind proxies (see app/core/clientip.py).
    client_ip_header: str | None = None  # "cf-connecting-ip" behind Cloudflare
    trusted_proxy_hops: int = 0  # 1 behind a single load balancer (e.g. Render without Cloudflare)
    # Shared with the Next.js server (BFF_SECRET there): lets it forward visitors' IPs (X-Client-IP)
    # so per-IP limits apply to customers, not to the BFF itself.
    bff_secret: SecretStr | None = None

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    frontend_url: str = "http://localhost:3000"
    sentry_dsn: str | None = None

    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: SecretStr | None = None
    media_folder: str = "hsc"  # per-environment folder, e.g. hsc-staging

    inventory_hold_seconds: int = 15 * 60  # how long checkout holds stock awaiting payment

    # Pricing policy (business decisions — change via env, not code).
    prices_include_tax: bool = True  # Indian retail norm: listed price is GST-inclusive
    tax_rate_bps: int = 1800  # 18.00% GST
    shipping_flat_paise: int = 9900  # ₹99
    free_shipping_threshold_paise: int = 99900  # free shipping from ₹999 (after discount)
    max_cart_item_quantity: int = 20
    max_cart_lines: int = 50
    return_window_days: int = 7

    # Email over SMTP (SES, Brevo, Resend, Zoho...). Empty host = console logging in dev/test.
    smtp_host: str | None = None
    smtp_port: int = 587  # 587 STARTTLS, 465 implicit TLS
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    email_from: str = "The Hot Smoothie Co. <hello@thehotsmoothie.co>"

    # "dev" = simulated gateway for local development / E2E tests (refused in production).
    payments_provider: Literal["razorpay", "dev"] = "razorpay"

    # Payments (Razorpay). Empty = payment endpoints return 503.
    razorpay_key_id: str | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None

    # Shipping (Shiprocket). Empty = shipping endpoints return 503.
    shiprocket_email: str | None = None
    shiprocket_password: SecretStr | None = None
    shiprocket_pickup_location: str = "Primary"  # pickup location *name* configured in Shiprocket
    shipping_webhook_token: SecretStr | None = None  # sent by Shiprocket as x-api-key
    warehouse_pincode: str = "110001"
    default_package_cm: tuple[int, int, int] = (45, 8, 8)  # rolled-poster tube L x B x H
    default_item_weight_grams: int = 250

    @field_validator("database_url")
    @classmethod
    def _asyncpg_url(cls, url: str) -> str:
        """Accept connection strings exactly as Neon/Supabase/RDS hand them out: force the asyncpg
        driver and translate libpq-only options asyncpg would reject."""
        parsed = make_url(url)
        if parsed.drivername in ("postgres", "postgresql", "postgresql+psycopg2", "postgresql+psycopg"):
            parsed = parsed.set(drivername="postgresql+asyncpg")
        query = dict(parsed.query)
        if "sslmode" in query:
            query["ssl"] = query.pop("sslmode")
        query.pop("channel_binding", None)
        return parsed.set(query=query).render_as_string(hide_password=False)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _forbid_dev_secrets_outside_dev(self) -> "Settings":
        if self.environment in ("staging", "production") and (
            self.jwt_secret.get_secret_value().startswith("dev-only") or len(self.jwt_secret) < 32
        ):
            raise ValueError("JWT_SECRET must be set to a strong value (>=32 chars) outside development")
        if self.is_production and not self.rate_limit_enabled:
            raise ValueError("RATE_LIMIT_ENABLED cannot be false in production")
        if self.is_production and self.payments_provider == "dev":
            raise ValueError("PAYMENTS_PROVIDER=dev cannot be used in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
