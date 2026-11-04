# Frontend (storefront + admin)

Next.js 16 (App Router, Cache Components / PPR), React 19, TypeScript.
The browser never talks to the API directly: Server Components and Server Actions call it from
the Next server (a BFF), with the session in httpOnly cookies (`hsc_at`, `hsc_rt`, `hsc_cart`).

The storefront reproduces the design in `../site` (static HTML/CSS from the Figma file) and is wired
to the API. The admin keeps its own look. They are separate root layouts, so navigating between them
is a full page load and neither one's CSS reaches the other.

```
src/app/(shop)         storefront root layout + storefront.css: site/css/styles.css as written, then
                       the few additions the design has no page for. No Tailwind here.
src/app/(shop)/(site)  pages inside the site chrome: home, shop, collection, product, cart, checkout,
                       order-confirmed, wishlist, about, faq, contact, gift-cards, shipping-returns,
                       search, 404, account (orders, returns, addresses), auth pages
src/components/sf      storefront components, using the design's class names
src/lib/content.ts     copy the design hard-codes, and how product/collection text maps to API fields
src/lib/site.ts        support email, drop date, delivery fee shown in copy
src/app/(admin)        admin (Tailwind + shadcn/ui): dashboard, orders, products (+CSV), categories,
                       collections, media, inventory, customers, reviews, coupons, notifications,
                       analytics, settings
src/app/actions        every write (Server Actions); each returns ActionResult
src/lib/api            typed client generated from the API's OpenAPI (`npm run api:types`)
src/proxy.ts           refreshes the access token before rendering
public/                the design's images (`assets/`) and the standalone /coming-soon page
e2e/                   Playwright: browse, cart, wishlist, register → checkout → pay → cancel, admin
```

## Editing store content

Posters and collections are managed in the admin. A few conventions make them fill the design:

| Design element | Where it comes from |
|---|---|
| Collection tagline + story | Collection description: tagline, blank line, story |
| Card chip | Tag `Bestseller`, `New drop` or `Croc’s pick` |
| "Only 250 made" | Tag `250 editions` |
| "Hang it if ..." | A description paragraph starting with those words |
| Product photos | First image is the poster (also shown framed); the rest are room shots |
| Croc's pick / "See it on your wall" | Slugs in `src/lib/content.ts` |

## Run locally

Needs the API on `:8000` (see `backend/README.md`), seeded with `python -m scripts.seed_site`,
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
