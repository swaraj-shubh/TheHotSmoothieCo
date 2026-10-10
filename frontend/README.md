# Frontend (storefront + admin)

Next.js 16 (App Router, Cache Components / PPR), React 19, TypeScript, Tailwind v4, shadcn/ui.
The browser never talks to the API directly: Server Components and Server Actions call it from
the Next server (a BFF), with the session in httpOnly cookies (`hsc_at`, `hsc_rt`, `hsc_cart`).

```
src/app/(shop)      storefront: home, shop, category/collection, product, search, cart, checkout,
                    wishlist, account (orders, returns, addresses), auth pages
src/app/admin       admin: dashboard, orders, products (+CSV), categories, collections, media,
                    inventory, customers, reviews, coupons, notifications, analytics, settings
src/app/actions     every write (Server Actions); each returns ActionResult
src/lib/api         typed client generated from the API's OpenAPI (`npm run api:types`)
src/proxy.ts        refreshes the access token before rendering
e2e/                Playwright: browse, search, cart, register → checkout → pay → cancel/refund, admin
```

## Run locally

Needs the API on `:8000` (see `backend/README.md`), seeded with `python -m scripts.seed_demo`,
and started with `PAYMENTS_PROVIDER=dev` to get a "simulate payment" button instead of Razorpay.

```bash
cp .env.example .env.local      # BFF_SECRET must equal the API's
npm ci
npm run dev                     # http://localhost:3000, admin at /admin
```

## Checks

```bash
npm run lint && npm run typecheck && npm run build
npx playwright install chromium
E2E_ADMIN_EMAIL=… E2E_ADMIN_PASSWORD=… npm run e2e     # builds must exist; starts `next start` on :3100
```

Re-running E2E many times in a few minutes trips the API's login rate limit; flush Redis
(`redis-cli FLUSHDB`) between runs locally. CI uses a fresh Redis.

After changing API schemas: `npm run api:types` (CI fails if the generated types are stale).
