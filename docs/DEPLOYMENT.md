# Deployment

Initial stack: **Render** (API + worker) · **Neon or Supabase** (Postgres) · **Upstash** (Redis) ·
**Cloudinary** (images) · **Cloudflare** (DNS/CDN/WAF) · **Vercel** (Next.js) · **GitHub Actions** (CI/CD).
Everything is reached through environment variables, so any piece can be swapped later (see the
portability table in ARCHITECTURE.md).

## 1. One-time setup

Do each step for **staging** (test credentials) and then **production**.

1. **Postgres**
   - *Neon*: create a project in `aws-ap-south-1` (Mumbai). Copy the **pooled** connection string
     (host contains `-pooler`) for the app, and the **direct** one for backups/migrations from your laptop.
   - *Supabase*: create a project in Mumbai. Use the transaction pooler (port `6543`) for the app.
   - Paste the connection string as the provider gives it (`postgresql://…?sslmode=require…` is
     converted for asyncpg automatically) and set `DB_PGBOUNCER=true` for pooler URLs.
   - Extensions needed: `pg_trgm` (created by the migrations; available on both providers).
2. **Redis**: Upstash database in Mumbai; copy the `rediss://` URL.
3. **Cloudinary**: copy cloud name, API key and secret; choose `MEDIA_FOLDER` per environment.
4. **Email**: pick an SMTP provider, verify your sending domain (SPF + DKIM + DMARC records in
   Cloudflare DNS), and copy the SMTP credentials.
5. **Razorpay**: copy API keys (test keys for staging). Under *Webhooks* add
   `https://API_DOMAIN/api/v1/webhooks/razorpay` with a secret and events `payment.captured`,
   `payment.authorized`, `payment.failed`, `order.paid`, `refund.processed`, `refund.failed`.
6. **Shiprocket**: create an API user, set the pickup location name, and configure the tracking
   webhook `https://API_DOMAIN/api/v1/webhooks/shipping` with token = `SHIPPING_WEBHOOK_TOKEN`.
7. **Render**: *New → Blueprint* → select this repo (`render.yaml`). Fill the `hsc-secrets` env
   group (see ENVIRONMENT.md). Set `ENVIRONMENT=staging` in the staging Blueprint.
   For each service, copy its **Deploy Hook URL** (Settings → Deploy Hook).
8. **Cloudflare**: add the domain; `api` CNAME → the Render service hostname (proxied, orange cloud).
   SSL mode *Full (strict)*. Keep `CLIENT_IP_HEADER=cf-connecting-ip` (see SECURITY.md).
9. **GitHub**: create environments `staging` and `production` (add required reviewers to
   `production`). In each, add secrets `RENDER_DEPLOY_HOOK_API`, `RENDER_DEPLOY_HOOK_WORKER` and
   the variable `API_URL` (e.g. `https://api.example.com`). Protect `main` (PR + passing checks).
10. **Vercel (storefront + admin)**: *Add New → Project* → this repo, root directory `frontend`.
    Environment variables (per environment): `API_URL` (the API's public URL), `BFF_SECRET`
    (same value as the API's — generate with `openssl rand -hex 32`), `NEXT_PUBLIC_SITE_URL`
    (e.g. `https://example.com`). Region `bom1` (Mumbai), next to the API. Point the apex/`www`
    domain at Vercel in Cloudflare (DNS only, grey cloud, as Vercel recommends). Set the API's
    `CORS_ORIGINS`/`FRONTEND_URL` to that domain. The site builds against the live API (it
    prerenders the catalog), so deploy the API first.
11. **First admin** (from your laptop, against the environment's direct DB URL):
    ```bash
    cd backend
    DATABASE_URL='postgresql+asyncpg://…direct…' python -m scripts.create_admin you@domain.com "Your Name"
    ```

### Low-cost mode (no separate worker)

Render's free web tier sleeps when idle and background workers are a paid service. To start on a
single service, delete the `hsc-worker` service and set `RUN_WORKER_IN_API=true` on the API. Jobs
then run inside the API process (still safe with several instances — every job takes a Postgres
advisory lock). Caveat: on a sleeping free instance, jobs (emails, order expiry) only run while it's
awake. Move to the dedicated worker (flip the flag back, re-add the service) once there's revenue.

## 2. Release flow

```
PR ──► checks: lint · types · migrations (up/down/up + check) · unit · integration + e2e · pip-audit
       image: docker build · smoke test · Trivy scan
merge to main ──► same checks ──► deploy staging (deploy hooks) ──► wait for /health/ready
frontend (any PR/main): API types in sync · eslint · tsc · next build · Playwright vs a seeded API
       Vercel builds a preview per PR and deploys production from main on its own
"Run workflow" (deploy_production=true) or tag v1.2.3 ──► checks ──► approval ──► deploy production ──► health
```

On every deploy Render runs `alembic upgrade head` as the **pre-deploy command**: if a migration
fails, the old version keeps serving and the deploy is marked failed. Migrations must be backward
compatible with the previous app version (expand → contract, see DATABASE.md), because old and new
instances overlap during a rolling deploy.

## 3. Rollback

- **Code**: Render → service → *Events* → redeploy the previous successful deploy (seconds).
  Or `git revert` + merge for a tracked rollback.
- **Schema**: migrations are additive by policy, so the previous code runs on the new schema.
  Only run `alembic downgrade` for a migration known to be destructive-safe, and never before
  taking a backup.
- **Data**: see the restore procedure in DATABASE.md.

## 4. Operations

| What | How |
|---|---|
| Errors | Sentry (API + worker), alerts on new issues |
| Uptime | External monitor (Better Stack, UptimeRobot…) on `/health/ready` (API + DB + Redis) and `/health/worker` (heartbeat ≤ 30 s) |
| Logs | Render log stream (JSON, one line per request with `request_id`); add a log drain (Better Stack, Datadog…) when retention matters |
| Dead letters | Admin → notifications `?status=FAILED`; failed webhooks counted on the dashboard (`webhook_events.status = FAILED`) |
| Capacity | ~90 req/s per API worker core measured; raise `numInstances` / `WEB_CONCURRENCY` (keep DB connections within the provider limit: `instances × WEB_CONCURRENCY × (DB_POOL_SIZE + DB_MAX_OVERFLOW)`) |

## 5. Moving to AWS later

Same image, same commands, new endpoints:

1. **RDS PostgreSQL** (Multi-AZ, PITR on): `pg_dump` from the provider → `pg_restore` into RDS
   during a short maintenance window (or logical replication for zero downtime), then switch
   `DATABASE_URL`. Use RDS Proxy with `DB_PGBOUNCER=true` if connection counts grow.
2. **ElastiCache Redis**: switch `REDIS_URL` (nothing in Redis needs migrating).
3. **ECS Fargate**: two services from the ECR image: API (default CMD, behind an ALB with
   health check `/health/ready`, `TRUSTED_PROXY_HOPS=1` or CloudFront's client-IP header) and worker
   (`python -m app.workers`). Run `alembic upgrade head` as a one-off task before each deploy.
   Secrets from AWS Secrets Manager.
4. **S3 + CloudFront** for media: implement `MediaStorage` for S3 (`upload`, `delete`, `url_for`)
   and copy existing assets; product URLs stored in the DB need a one-off rewrite migration.
5. **SES** for email: change `SMTP_*`.
