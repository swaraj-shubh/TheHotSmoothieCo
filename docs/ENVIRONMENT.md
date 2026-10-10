# Environment

All configuration comes from environment variables (`.env` in development only — never committed).
Source of truth: `backend/app/core/config.py`; template: `backend/.env.example`.
In staging/production, set values as platform secrets (Render env group `hsc-secrets`).

## Environments

| | development | test | staging | production |
|---|---|---|---|---|
| `ENVIRONMENT` | `development` | `test` (set by pytest) | `staging` | `production` |
| API docs (`/docs`) | on | on | on | **off** |
| Weak `JWT_SECRET` | allowed | allowed | **refused** | **refused** |
| `RATE_LIMIT_ENABLED=false` | allowed | allowed | allowed | **refused** |
| Email without SMTP | logged to console | logged | retried → dead letter | retried → dead letter |
| Payments / shipping / media without credentials | endpoints return 503; everything else works | | | |

Staging should mirror production with **test** credentials (Razorpay test keys, a separate
Cloudinary folder via `MEDIA_FOLDER`, a separate database and Redis).

## Core

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `test` / `staging` / `production` |
| `DEBUG` | `false` | Pretty console logs instead of JSON |
| `APP_NAME` | `TheHotSmoothieCo` | Used in API title |
| `DATABASE_URL` | local | Paste as the provider gives it; `postgres://`, `sslmode=` and `channel_binding=` are normalised for asyncpg |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `10` / `10` | Connections per process. Keep `(pool+overflow) × processes` under the provider's limit |
| `DB_PGBOUNCER` | `false` | `true` when `DATABASE_URL` is a transaction-mode pooler (Supabase :6543, Neon `-pooler` host, RDS Proxy) |
| `REDIS_URL` | local | `redis://` or `rediss://` (Upstash requires TLS) |
| `JWT_SECRET` | dev value | ≥32 random chars outside development. Rotating it signs everyone out |
| `JWT_ALGORITHM` | `HS256` | |
| `ACCESS_TOKEN_TTL_SECONDS` | `900` | Access token lifetime |
| `REFRESH_TOKEN_TTL_SECONDS` | `2592000` | Sliding session lifetime (30 days) |
| `EMAIL_TOKEN_TTL_SECONDS` | `86400` | Email verification link lifetime |
| `PASSWORD_RESET_TTL_SECONDS` | `3600` | Reset link lifetime |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | JSON list of allowed frontend origins |
| `FRONTEND_URL` | `http://localhost:3000` | Used to build links in emails |
| `SENTRY_DSN` | — | Error tracking for API and worker |
| `RATE_LIMIT_ENABLED` | `true` | Load testing only |
| `CLIENT_IP_HEADER` | — | `cf-connecting-ip` behind Cloudflare (see SECURITY.md) |
| `TRUSTED_PROXY_HOPS` | `0` | `1` behind a single load balancer without Cloudflare |
| `BFF_SECRET` | — | Shared with the Next.js server. Lets it forward each visitor's IP (`X-Client-IP`) so per-IP limits apply to customers, not to the BFF; its own cache-refill reads skip IP limits |
| `RUN_WORKER_IN_API` | `false` | Run background jobs inside the API process (single-service/free-tier hosting) |

## Commerce policy

| Variable | Default | Description |
|---|---|---|
| `PRICES_INCLUDE_TAX` | `true` | Listed prices are GST-inclusive |
| `TAX_RATE_BPS` | `1800` | GST in basis points (18.00%). **Confirm the rate for printed posters with your accountant** |
| `SHIPPING_FLAT_PAISE` | `9900` | ₹99 below the free-shipping threshold |
| `FREE_SHIPPING_THRESHOLD_PAISE` | `99900` | Free shipping from ₹999 (after discount) |
| `INVENTORY_HOLD_SECONDS` | `900` | How long checkout holds stock awaiting payment |
| `MAX_CART_ITEM_QUANTITY` | `20` | Per line |
| `MAX_CART_LINES` | `50` | Distinct items per cart |
| `RETURN_WINDOW_DAYS` | `7` | Days after delivery a return can be requested |

## Media (Cloudinary)

| Variable | Description |
|---|---|
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | From the Cloudinary console. Missing → upload endpoints return 503 |
| `MEDIA_FOLDER` (`hsc`) | Folder prefix; use a different one per environment (`hsc-staging`) |

## Email (SMTP)

| Variable | Default | Description |
|---|---|---|
| `SMTP_HOST` | — | Any provider (SES, Brevo, Resend, Zoho…). Empty in dev = console |
| `SMTP_PORT` | `587` | 587 STARTTLS or 465 implicit TLS |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | — | |
| `EMAIL_FROM` | `The Hot Smoothie Co. <hello@thehotsmoothie.co>` | Must be a verified sender/domain (SPF, DKIM, DMARC) |

## Payments (Razorpay)

| Variable | Description |
|---|---|
| `PAYMENTS_PROVIDER` | `razorpay` (default) or `dev`: a simulated gateway for local development and E2E tests (`POST /payments/orders/{id}/simulate`); refused in production |
| `RAZORPAY_KEY_ID` | Public key id (sent to the checkout widget) |
| `RAZORPAY_KEY_SECRET` | API secret (server only) |
| `RAZORPAY_WEBHOOK_SECRET` | Secret configured on the webhook in the Razorpay dashboard |

## Shipping (Shiprocket)

| Variable | Default | Description |
|---|---|---|
| `SHIPROCKET_EMAIL`, `SHIPROCKET_PASSWORD` | — | A dedicated **API user** (Settings → API), not your login |
| `SHIPROCKET_PICKUP_LOCATION` | `Primary` | Pickup location *name* as configured in Shiprocket |
| `SHIPPING_WEBHOOK_TOKEN` | — | Token Shiprocket sends as `x-api-key` on tracking webhooks |
| `WAREHOUSE_PINCODE` | `110001` | Pickup PIN code, used for serviceability checks |
| `DEFAULT_PACKAGE_CM` | `[45, 8, 8]` | Package L×B×H in cm (rolled-poster tube) |
| `DEFAULT_ITEM_WEIGHT_GRAMS` | `250` | Used when a variant has no weight |
