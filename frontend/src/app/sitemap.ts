import type { MetadataRoute } from "next"
import { cacheLife } from "next/cache"

import type { CategoryNode } from "@/lib/api/types"
import { getCategories, getCollections, getProducts } from "@/lib/catalog"
import { SITE } from "@/lib/site"

const MAX_PRODUCTS = 5000 // one sitemap file holds up to 50k URLs; split with generateSitemaps beyond that

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  "use cache"
  cacheLife("hours")
  const [categories, collections] = await Promise.all([getCategories(), getCollections()])
  const flat = (nodes: CategoryNode[]): CategoryNode[] => nodes.flatMap((n) => [n, ...flat(n.children ?? [])])

  const products = []
  let cursor: string | undefined
  while (products.length < MAX_PRODUCTS) {
    const page = await getProducts({ limit: 100, cursor })
    products.push(...page.items)
    if (!page.next_cursor) break
    cursor = page.next_cursor
  }

  return [
    { url: SITE.url, changeFrequency: "daily", priority: 1 },
    { url: `${SITE.url}/shop`, changeFrequency: "daily", priority: 0.9 },
    ...flat(categories).map((c) => ({ url: `${SITE.url}/category/${c.slug}`, changeFrequency: "weekly" as const, priority: 0.8 })),
    ...collections.map((c) => ({ url: `${SITE.url}/collection/${c.slug}`, changeFrequency: "weekly" as const, priority: 0.7 })),
    ...products.map((p) => ({ url: `${SITE.url}/product/${p.slug}`, changeFrequency: "weekly" as const, priority: 0.8 })),
  ]
}
