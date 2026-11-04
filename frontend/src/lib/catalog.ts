import "server-only"

import { cacheLife, cacheTag } from "next/cache"

import { publicApi, unwrap, unwrapOrNull } from "./api/client"
import type {
  AttributeOut,
  BannerOut,
  CategoryNode,
  CollectionOut,
  Page,
  ProductCard,
  ProductDetail,
  PublicReview,
  ReviewSummary,
  SearchPage,
} from "./api/types"

/*
 * Public catalog reads, shared by every visitor and cached on the server ('use cache').
 * Admin edits call revalidateTag("catalog") so changes appear without a redeploy.
 * If the API is briefly unreachable, a short-lived empty result is cached instead of failing the
 * page (`seconds` lifetime -> heals on the next request).
 */

export type ProductQuery = {
  category?: string
  collection?: string
  tag?: string
  sort?: "newest" | "price_asc" | "price_desc" | "relevance"
  min_price?: number
  max_price?: number
  in_stock?: boolean
  attr?: string[]
  cursor?: string
  limit?: number
}

const EMPTY_PAGE: Page<ProductCard> = { items: [], next_cursor: null }

/**
 * A page's own data: an API failure at request time reaches the error page, but during `next build`
 * it must not fail the deploy. The short lifetime keeps that result out of the prerendered shell,
 * so the real page is fetched on the first visit rather than a false 404 being baked in.
 */
async function pageData<T>(life: "minutes" | "hours", load: () => Promise<T>, fallback: T): Promise<T> {
  try {
    const data = await load()
    if (life === "hours") cacheLife("hours")
    else cacheLife("minutes")
    return data
  } catch (err) {
    if (process.env.NEXT_PHASE !== "phase-production-build") throw err
    console.warn("Catalog API failed during the build; this page will render on first visit:", err)
    cacheLife("seconds")
    return fallback
  }
}

export async function getCategories(): Promise<CategoryNode[]> {
  "use cache"
  cacheTag("catalog", "categories")
  try {
    const tree = unwrap(await publicApi.GET("/api/v1/categories"))
    cacheLife("hours")
    return tree
  } catch {
    cacheLife("seconds")
    return []
  }
}

export async function getCategory(slug: string): Promise<CategoryNode | null> {
  "use cache"
  cacheLife("hours")
  cacheTag("catalog", "categories")
  return unwrapOrNull(await publicApi.GET("/api/v1/categories/{slug}", { params: { path: { slug } } }))
}

export async function getAttributes(): Promise<AttributeOut[]> {
  "use cache"
  cacheTag("catalog", "attributes")
  try {
    const attrs = unwrap(await publicApi.GET("/api/v1/attributes"))
    cacheLife("hours")
    return attrs
  } catch {
    cacheLife("seconds")
    return []
  }
}

export async function getCollections(): Promise<CollectionOut[]> {
  "use cache"
  cacheTag("catalog", "collections")
  try {
    const cols = unwrap(await publicApi.GET("/api/v1/collections"))
    cacheLife("hours")
    return cols
  } catch {
    cacheLife("seconds")
    return []
  }
}

export async function getCollection(slug: string): Promise<CollectionOut | null> {
  "use cache"
  cacheTag("catalog", "collections")
  return pageData("hours", async () => unwrapOrNull(await publicApi.GET("/api/v1/collections/{slug}", { params: { path: { slug } } })), null)
}

export async function getProducts(query: ProductQuery): Promise<Page<ProductCard>> {
  "use cache"
  cacheTag("catalog", "products")
  try {
    const page = unwrap(
      await publicApi.GET("/api/v1/products", {
        params: { query: { ...query, sort: query.sort === "relevance" ? "newest" : query.sort } },
      }),
    )
    cacheLife("minutes")
    return page
  } catch {
    cacheLife("seconds")
    return EMPTY_PAGE
  }
}

/** Product detail incl. availability. A minute of staleness is fine: the cart and checkout always
 *  re-check live stock and prices. */
export async function getProduct(slug: string): Promise<ProductDetail | null> {
  "use cache"
  cacheTag("catalog", "products", `product:${slug}`)
  return pageData("minutes", async () => unwrapOrNull(await publicApi.GET("/api/v1/products/{slug}", { params: { path: { slug } } })), null)
}

export async function searchProducts(q: string, query: ProductQuery): Promise<SearchPage> {
  "use cache"
  cacheTag("catalog", "products")
  try {
    const page = unwrap(await publicApi.GET("/api/v1/search", { params: { query: { q, ...query } } }))
    cacheLife("minutes")
    return page
  } catch {
    cacheLife("seconds")
    return { items: [], next_cursor: null, fuzzy: false }
  }
}

export async function getReviews(slug: string, cursor?: string): Promise<{
  page: Page<PublicReview>
  summary: ReviewSummary | null
}> {
  "use cache"
  cacheTag("reviews", `reviews:${slug}`)
  return pageData(
    "minutes",
    async () => {
      const [page, summary] = await Promise.all([
        publicApi.GET("/api/v1/products/{slug}/reviews", { params: { path: { slug }, query: { cursor, limit: 10 } } }),
        publicApi.GET("/api/v1/products/{slug}/reviews/summary", { params: { path: { slug } } }),
      ])
      return { page: unwrapOrNull(page) ?? { items: [] }, summary: unwrapOrNull(summary) }
    },
    { page: { items: [] }, summary: null },
  )
}

export async function getBanners(placement: "HOME_HERO" | "HOME_STRIP" | "SHOP_TOP"): Promise<BannerOut[]> {
  "use cache"
  cacheTag("banners")
  try {
    const banners = unwrap(await publicApi.GET("/api/v1/banners", { params: { query: { placement } } }))
    cacheLife("minutes")
    return banners
  } catch {
    cacheLife("seconds")
    return []
  }
}

// The two below only combine cached calls. They have no cache of their own, so a failed fetch stays
// short-lived instead of an empty result being held for the outer cache's lifetime.
export type CardExtra = { collection?: string; collectionSlug?: string; chip?: string }

const CHIPS: Record<string, string> = { bestseller: "Bestseller", "new-drop": "New drop", "crocs-pick": "Croc’s pick" }

/** Every active product. ponytail: stops at 500; the shop filters client-side like the design does,
 *  so move filtering to the API if the catalogue outgrows that. */
export async function getAllProducts(): Promise<ProductCard[]> {
  const all: ProductCard[] = []
  let cursor: string | undefined
  do {
    const page = await getProducts({ limit: 100, cursor })
    all.push(...page.items)
    cursor = page.next_cursor ?? undefined
  } while (cursor && all.length < 500)
  return all
}

/** What a product card shows beyond the list API's fields: its collection name and chip.
 *  Derived from the collection and tag filters, keyed by product id. */
export async function getCardExtras(): Promise<Record<string, CardExtra>> {
  const extras: Record<string, CardExtra> = {}
  const of = (id: string) => (extras[id] ??= {})
  const [collections, ...chips] = await Promise.all([
    getCollections(),
    ...Object.keys(CHIPS).map((tag) => getProducts({ tag, limit: 100 }).then((p) => [tag, p.items] as const)),
  ])
  const lists = await Promise.all(collections.map((c) => getProducts({ collection: c.slug, limit: 100 })))
  collections.forEach((c, i) =>
    lists[i].items.forEach((p) => {
      of(p.id).collection ??= c.name
      of(p.id).collectionSlug ??= c.slug
    }),
  )
  for (const [tag, items] of chips) for (const p of items) of(p.id).chip ??= CHIPS[tag]
  return extras
}

/** Slugs to prerender at build time (bestsellers). Falls back to a placeholder that 404s so the
 *  build never depends on the API being reachable. */
export async function getPrerenderSlugs(): Promise<string[]> {
  try {
    const page = unwrap(await publicApi.GET("/api/v1/products", { params: { query: { limit: 24 } } }))
    return page.items.length ? page.items.map((p) => p.slug) : ["__placeholder__"]
  } catch {
    return ["__placeholder__"]
  }
}
