# TheHotSmoothieCo — Backend

FastAPI modular monolith for the TheHotSmoothieCo art & poster store.

## Run locally (hosted Neon + Upstash + Cloudinary)

The day-to-day setup: no local Postgres/Redis, just free hosted services.

### 1. `.env` (once)

```bash
cp .env.example .env
```

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | [Neon](https://console.neon.tech) → project (region Singapore) → **Connect** → copy the string as-is (`postgresql://…?sslmode=require&channel_binding=require`). The app converts it for asyncpg. |
| `DB_PGBOUNCER=true` | Required when the Neon host contains `-pooler` (pooling on). Leave `false` for the direct host. |
| `REDIS_URL` | [Upstash](https://console.upstash.com) → Create Database (Singapore, free) → **Connect → TCP**. Must start with `rediss://`. |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | [Cloudinary](https://console.cloudinary.com) → Settings → API Keys. |
| `MEDIA_FOLDER=hsc-dev` | Cloudinary folder; use a different one per environment. |
| `RUN_WORKER_IN_API=true` | Runs background jobs (emails, stock-hold expiry) inside the API, so no separate worker process. |
| `PAYMENTS_PROVIDER=dev` | Checkout shows a "Simulate payment" button; no Razorpay keys needed. |
| `BFF_SECRET` | Any string; must equal `BFF_SECRET` in `frontend/.env.local`. |

Optional until go-live: leave `SMTP_HOST` empty (emails are printed to the API log), Shiprocket blank
(courier booking returns 503, everything else works), Razorpay blank (with `PAYMENTS_PROVIDER=dev`).

### 2. Install + database (once, or after pulling new migrations)

```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head                                           # create/upgrade tables
.venv/bin/python -m scripts.create_admin you@thehotsmoothie.co "Your Name"  # SUPER_ADMIN; prompts for a password (12+ chars)
.venv/bin/python -m scripts.seed_demo     # 8 demo posters + coupon WELCOME10 (uploads sampleImage/a_31.webp)
.venv/bin/python -m scripts.seed_demo2    # "Mahadev & Nandi Under the Moon" with the 4 sampleImage photos
```

All three scripts are safe to re-run. Re-running `create_admin` with the same email resets that
admin's password. The seed scripts refuse to run when `ENVIRONMENT=production`.

### 3. Run (every time)

```bash
cd backend && RUN_WORKER_IN_API=true .venv/bin/uvicorn app.main:app --reload --port 8000
```

- Check: http://localhost:8000/health/ready → `{"database":"ok","redis":"ok"}`; API docs at http://localhost:8000/docs.
- Port busy? `kill $(lsof -t -i:8000)`.
- Then the frontend: `cd frontend && npm run dev` → http://localhost:3000 (admin at `/admin`, log in with the `create_admin` account).

### Logins

Everyone signs in at `/login`; access depends on roles (enforced by the API on every request).
New staff register as normal customers, then a SUPER_ADMIN ticks their roles in **Admin → Settings → Staff**.

| Role | Can |
|---|---|
| (none) | Customer: shop, checkout, orders, returns, reviews |
| SUPER_ADMIN | Everything, incl. staff roles (`create_admin` gives this) |
| ADMIN | Everything except staff roles; deactivate customers, audit log |
| PRODUCT_MANAGER | Products, variants, images, categories, collections, CSV, reviews |
| INVENTORY_MANAGER | Stock levels and adjustments |
| ORDER_MANAGER | Orders, shipping, returns and refunds |
| CUSTOMER_SUPPORT | View customers/orders/returns, retry emails, moderate reviews |
| MARKETING_MANAGER | Coupons, banners, email templates, analytics |

### Deploy on Vercel (temporary; Render later)

Project settings: **Root Directory = `backend`**, framework auto-detected (FastAPI, entrypoint `index.py`,
region `bom1` from `vercel.json`). Set these env vars in Vercel (same names as `.env`):

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` (or `staging` while testing) |
| `DATABASE_URL`, `DB_PGBOUNCER=true` | Neon **pooled** (`-pooler`) string; use a separate prod DB/branch |
| `DB_POOL_SIZE=1`, `DB_MAX_OVERFLOW=0` | Every serverless instance has its own pool; keep it tiny |
| `REDIS_URL` | Upstash `rediss://…` |
| `JWT_SECRET` | 32+ random chars (`openssl rand -hex 32`); the app refuses to start in staging/production without it |
| `CORS_ORIGINS`, `FRONTEND_URL` | your frontend URL, e.g. `["https://shop.example.com"]` |
| `BFF_SECRET` | same value as the frontend's `BFF_SECRET` |
| `CLOUDINARY_*`, `MEDIA_FOLDER=hsc-prod` | as above |
| `RUN_WORKER_IN_API=false` | no long-lived process on Vercel |
| `CRON_SECRET` | random string, used by the job trigger below |
| `PAYMENTS_PROVIDER=razorpay` + keys | required in production (`dev` is refused) |

Run migrations from your machine against the production `DATABASE_URL` (`alembic upgrade head`); Vercel does not run them.

**Background jobs.** Vercel can't run `python -m app.workers`, so a scheduler must call
`GET https://<api>/internal/cron` with header `Authorization: Bearer <CRON_SECRET>` **every minute**; each job
still runs on its own interval (emails every 5 s of backlog per tick, order expiry 1 min, etc.).
Use [cron-job.org](https://cron-job.org) (free, 1-minute) — Vercel Cron on the Hobby plan only runs daily.
Without it: no emails, unpaid orders never release stock, no tracking sync. Emails are delayed up to a minute.

Limits to know: Hobby functions time out at 10 s by default (60 s max), CSV import and image uploads should
stay small; cold starts add ~1–2 s to the first request after idle. Move to Render (`../render.yaml`) when ready: set
`RUN_WORKER_IN_API=true` or run the worker, and drop the cron.

### Alternative: everything in Docker

```bash
cp .env.example .env
docker compose up --build          # postgres + redis + migrations + API on :8000 + worker
```

With a separate worker instead of `RUN_WORKER_IN_API`: `python -m app.workers`.

## Checks (same as CI)

```bash
ruff check . && ruff format --check . && mypy app
alembic upgrade head && alembic check   # fails if models changed without a migration
pytest -q tests/unit                    # pure logic
pytest -q tests/integration tests/e2e   # needs DATABASE_URL / REDIS_URL pointing at a throwaway DB
python -m scripts.gen_api_index         # refresh docs/API.md after changing endpoints
```

## Layout

```
app/
  core/          config, database, redis, logging + request middleware, errors, security, rate limiting
  auth/          register/login, refresh rotation, sessions, email verification, password reset, RBAC deps
  users/         user model, roles, profile endpoints
  health/        /health/live (process) and /health/ready (DB + Redis)
  catalog/       categories, collections, tags, attributes, products, variants, media (public + admin)
  inventory/     stock ledger, reservations (reserve/commit/release/expire), admin stock tools
  media/         MediaStorage interface + Cloudinary implementation, image sniffing
  cart/          guest + user carts, merge on login, live pricing, coupon preview
  wishlist/      saved products/variants, move to cart
  coupons/       rules, atomic redemption limits, admin CRUD
  checkout/      pricing maths (pure, unit-tested) + cart -> order transaction
  orders/        order snapshots, state machine + history, cancel/refund/returns (lifecycle.py), admin desk
  payments/      PaymentProvider + Razorpay, idempotent capture/refund handling
  shipping/      ShippingProvider + Shiprocket, shipments, tracking -> order status
  webhooks/      signed inbound webhooks, dedupe, dead-letter (webhook_events)
  notifications/ transactional outbox, templates (staff-editable), SMTP sender, retries + dead-letter
  reviews/       moderated reviews, verified-purchase badge, photos, product rating aggregate
  search/        SearchBackend + Postgres full-text (weighted, prefix) with trigram typo fallback
  workers/       `python -m app.workers`: scheduler with Postgres advisory locks
  admin/         dashboard, analytics, customers, staff roles, banners, audit-log API
  audit/         middleware recording every admin mutation (incl. denied attempts), secrets redacted
migrations/      Alembic — every schema change goes through here
tests/           integration tests run against real Postgres + Redis
```

Each module: `models.py` → `repository.py` (queries) → `service.py` (business rules, transactions) → `router.py` (HTTP only).

## Auth model

- **Access token**: JWT, 15 min, `Authorization: Bearer`. Every request also checks the session row, so logout / deactivation is immediate.
- **Refresh token**: opaque, stored hashed, rotated on every use. Replaying a rotated token revokes the session (theft detection).
- The Next.js app should keep tokens in **httpOnly cookies on its own domain** (BFF route handlers) and call this API with the bearer header — tokens never touch browser JS, and the API needs no CSRF handling.
- Errors: `{"success": false, "error": {"code": "...", "message": "..."}}` with stable codes.

## Status

- Phase 1 (foundation + auth) — done
- Phase 2 (addresses, catalog, variants, media, inventory) — done
- Phase 3 (cart, wishlist, coupons, checkout, order creation) — done
- Phase 4 (payments, webhooks, refunds, returns, shipping, admin order desk) — done
- Phase 5 (notifications, background worker, reviews, search) — done
- Phase 6 (admin dashboard, analytics, customers, roles, audit log, banners, CSV import/export) — done
- Phase 7 (security hardening, performance verification, CI/CD, deployment config, docs) — done
- Next: Next.js storefront + admin

Full documentation lives in [`../docs`](../docs): architecture, API, database, deployment,
security, environment.

## Checkout model

- `POST /api/v1/checkout` with an `Idempotency-Key` header turns the cart into a `PENDING_PAYMENT` order in one transaction: live prices, coupon, totals, address snapshot, stock reservation, coupon redemption. Retries with the same key return the same order.
- Optional `expected_total_paise`: if the server total differs, the order is refused with `PRICE_CHANGED` instead of charging a surprise amount.
- Unpaid orders auto-cancel after `INVENTORY_HOLD_SECONDS` (`orders.service.expire_unpaid`, scheduled by the worker in Phase 5), returning stock and the coupon use.
- Checkout requires login; guests can build a cart (`X-Cart-Token`) and `POST /cart/merge` after logging in.

## Admin

| Area | Endpoints | Roles |
|---|---|---|
| Overview | `GET /admin/dashboard` (cached 60 s) | any staff |
| Analytics | `GET /admin/analytics/{sales,top-products,customers}?from&to&interval` (IST buckets, net of refunds) | ADMIN, MARKETING_MANAGER |
| Customers | `GET/PATCH /admin/customers[/{id}]` (deactivate = signed out everywhere) | view: support; change: ADMIN |
| Staff roles | `GET /admin/users`, `PUT /admin/users/{id}/roles` (can't remove own SUPER_ADMIN) | SUPER_ADMIN |
| Audit log | `GET /admin/audit-logs?actor_id&target_id&since&until` | ADMIN |
| Banners | `/admin/banners` CRUD, public `GET /banners?placement=HOME_HERO` (scheduled) | MARKETING_MANAGER |
| Catalog CSV | `GET /admin/products/export.csv`, `POST /admin/products/import?dry_run=true` | PRODUCT_MANAGER |

Every POST/PUT/PATCH/DELETE under `/api/v1/admin` is written to `audit_logs`: who (snapshot of email + roles), what (route + target id), outcome (status code, so denied attempts show up), request ID, IP, and the JSON body with password/token/secret fields redacted. Uploads record size, not content.

CSV import is all-or-nothing and validates every row first; errors come back with row numbers. `dry_run` defaults to true. One row per variant; prices in rupees (`1499.00`); options as `size=A3; frame=Black`; blank optional cells leave existing values unchanged. Exports neutralise spreadsheet formulas (`=`, `+`, `-`, `@`).

## Background worker

`python -m app.workers` (same Docker image, different command). All durable work lives in Postgres; the worker only schedules. Each job holds a Postgres advisory lock while it runs, so any number of worker instances can run safely and a crashed worker's lock is released automatically.

| Job | Every | What |
|---|---|---|
| drain_notifications | 5 s | send queued emails; exponential backoff; FAILED after 6 tries (`GET /admin/notifications?status=FAILED`) |
| expire_unpaid_orders | 1 min | cancel unpaid orders past their window, release stock + coupon |
| reconcile_payments | 15 min | settle orders stuck in PAYMENT_PROCESSING by asking the gateway |
| sync_shipments | 30 min | poll courier tracking (fallback for missed webhooks) |
| abandoned_carts | 1 h | one reminder per idle cart (24–72 h), honours marketing opt-out |
| reindex_search | 6 h | refresh search documents (e.g. after category renames) |
| cleanup | 24 h | stale guest carts, expired tokens/sessions, old webhook logs |

Monitoring: the worker writes a `worker:heartbeat` key to Redis every second (60 s TTL); alert if it's missing.

## Payment model

1. `POST /checkout` -> order `PENDING_PAYMENT` (stock held).
2. `POST /payments/orders/{id}/initiate` -> Razorpay order details for the Checkout widget (idempotent).
3. Widget success -> `POST /payments/orders/{id}/verify` (signature checked, payment re-fetched from Razorpay).
4. Razorpay webhook confirms independently; both paths share one idempotent handler.

Guarantees (all tested): duplicate webhooks are no-ops; a payment landing after expiry/cancellation is auto-refunded; a second capture is auto-refunded; refunds are idempotent per key and can never exceed the captured amount; a gateway timeout leaves a refund PENDING (never retried blindly) until its webhook settles it. Failed webhook processing is stored in `webhook_events` (status `FAILED`) and the gateway's redelivery retries it.

ponytail: Shiprocket calls follow their public docs but haven't been exercised against a real account yet — verify in their sandbox once credentials are set.

## Catalog & inventory model

- Money is **integer paise** everywhere.
- Variant attributes are global (`size`, `frame`, `paper`…) so the storefront can filter across products: `GET /api/v1/products?attr=size:a3&attr=frame:black&in_stock=true`.
- Stock: `available = on_hand - reserved`. Checkout reserves; payment commits; cancel/timeout releases. All changes are single conditional UPDATEs plus DB CHECK constraints, and every change writes an `inventory_transactions` row. Tested: 100 concurrent buyers for 5 units → exactly 5 succeed.
