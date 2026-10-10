import Link from "next/link"
import { Suspense } from "react"

import { Button } from "@/components/ui/button"
import { getAttributes, getProducts, searchProducts, type ProductQuery } from "@/lib/catalog"

import { Filters } from "./filters"
import { ProductGrid, ProductGridSkeleton } from "./product-card"

type SP = Record<string, string | string[] | undefined>

const SORTS = new Set(["newest", "price_asc", "price_desc", "relevance"])
const PRICE_BANDS: Record<string, [number | undefined, number | undefined]> = {
  "under-500": [undefined, 50000],
  "500-1000": [50000, 100000],
  "1000-2000": [100000, 200000],
  "2000-plus": [200000, undefined],
}

/** URL search params -> a validated API query (unknown values are ignored, never forwarded). */
export function toQuery(sp: SP, base: ProductQuery = {}): ProductQuery {
  const one = (k: string) => (Array.isArray(sp[k]) ? sp[k]![0] : sp[k]) as string | undefined
  const many = (k: string) => [sp[k] ?? []].flat().filter(Boolean) as string[]
  const sort = one("sort")
  const [min, max] = PRICE_BANDS[one("price") ?? ""] ?? [undefined, undefined]
  const attr = ["size", "frame", "paper"].flatMap((code) =>
    many(code)
      .filter((v) => /^[a-z0-9-]{1,40}$/.test(v))
      .map((v) => `${code}:${v}`),
  )
  return {
    ...base,
    sort: sort && SORTS.has(sort) ? (sort as ProductQuery["sort"]) : base.sort,
    min_price: min,
    max_price: max,
    in_stock: one("in_stock") === "1" || undefined,
    attr: attr.length ? attr : undefined,
    cursor: one("cursor")?.slice(0, 500),
    limit: 24,
  }
}

async function Results({ searchParams, base, q }: { searchParams: Promise<SP>; base: ProductQuery; q?: string }) {
  const sp = await searchParams
  const query = toQuery(sp, base)
  const page = q ? await searchProducts(q, query) : await getProducts(query)
  const fuzzy = "fuzzy" in page && page.fuzzy === true

  if (!page.items.length) {
    return (
      <div className=" border border-dashed py-20 text-center">
        <p className="font-display text-3xl">Nothing here… yet</p>
        <p className="mt-2 text-muted-foreground">
          {q ? `No results for “${q}”.` : "No products match these filters."} Try removing a filter.
        </p>
        <Button asChild variant="outline" className="mt-6">
          <Link href="/shop">Browse everything</Link>
        </Button>
      </div>
    )
  }

  const nextParams = new URLSearchParams()
  for (const [k, v] of Object.entries(sp)) for (const x of [v ?? []].flat()) if (k !== "cursor") nextParams.append(k, x)
  const firstHref = `?${nextParams}`
  if (page.next_cursor) nextParams.set("cursor", page.next_cursor)

  return (
    <div className="space-y-8">
      {fuzzy && (
        <p className="rounded-lg bg-secondary px-4 py-3 text-sm text-secondary-foreground">
          No exact matches for “{q}”, showing the closest results.
        </p>
      )}
      <ProductGrid products={page.items} priorityCount={4} />
      <nav aria-label="Pagination" className="flex justify-center gap-3">
        {query.cursor && (
          <Button asChild variant="outline">
            <Link href={firstHref}>← Back to start</Link>
          </Button>
        )}
        {page.next_cursor && (
          <Button asChild>
            <Link href={`?${nextParams}`}>Next page →</Link>
          </Button>
        )}
      </nav>
    </div>
  )
}

export async function Listing({
  searchParams,
  base = {},
  q,
  showSort = true,
}: {
  searchParams: Promise<SP>
  base?: ProductQuery
  q?: string
  showSort?: boolean
}) {
  const attributes = await getAttributes()
  return (
    <div className="grid gap-8 lg:grid-cols-[220px_1fr]">
      <Suspense fallback={<div className="hidden lg:block" />}>
        <Filters attributes={attributes} showRelevance={!!q} showSort={showSort} />
      </Suspense>
      <div className="lg:col-start-2">
        <Suspense fallback={<ProductGridSkeleton />}>
          <Results searchParams={searchParams} base={base} q={q} />
        </Suspense>
      </div>
    </div>
  )
}
