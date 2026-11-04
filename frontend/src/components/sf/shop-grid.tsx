"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useState } from "react"

import type { CollectionOut, ProductCard } from "@/lib/api/types"
import type { CardExtra } from "@/lib/catalog"

import { Card } from "./card"

/** The site's shop controls: collection pills and sort, applied in the browser. */
export function ShopGrid({ products, extras, collections }: { products: ProductCard[]; extras: Record<string, CardExtra>; collections: CollectionOut[] }) {
  const params = useSearchParams()
  const [c, setC] = useState(params.get("c") ?? "all")
  const [onlyNew, setOnlyNew] = useState(params.get("new") === "1")
  const [sort, setSort] = useState("featured")

  let list = products.filter((p) => (c === "all" || extras[p.id]?.collectionSlug === c) && (!onlyNew || extras[p.id]?.chip === "New drop"))
  if (sort === "az") list = [...list].sort((a, b) => a.title.localeCompare(b.title))

  return (
    <>
      <section className="wrap" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 24, flexWrap: "wrap", paddingBottom: 32 }}>
        <div className="pill-group" role="radiogroup" aria-label="Filter by collection">
          {[{ slug: "all", name: "All" }, ...collections].map((x) => (
            <label key={x.slug} className="pill">
              <input
                type="radio"
                name="f"
                value={x.slug}
                checked={c === x.slug}
                onChange={() => {
                  setC(x.slug)
                  setOnlyNew(false)
                }}
              />
              <span>{x.name}</span>
            </label>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <span className="t-cap muted" aria-live="polite">
            {list.length} {list.length === 1 ? "poster" : "posters"}
          </span>
          <label className="sr-only" htmlFor="sort">
            Sort
          </label>
          <select className="input input--pill" id="sort" style={{ width: "auto" }} value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="featured">Featured</option>
            <option value="az">A to Z</option>
          </select>
        </div>
      </section>
      <section className="wrap section--tight" style={{ paddingTop: 0, paddingBottom: 96 }}>
        <div className="grid-products" id="grid">
          {list.length ? (
            list.map((p) => <Card key={p.id} product={p} extra={extras[p.id]} />)
          ) : (
            <div className="empty">
              <p className="t-head">Nothing here yet.</p>
              <p>The next drop is on its way.</p>
              <Link className="btn" href="/shop">
                [ See everything ]
              </Link>
            </div>
          )}
        </div>
      </section>
    </>
  )
}
