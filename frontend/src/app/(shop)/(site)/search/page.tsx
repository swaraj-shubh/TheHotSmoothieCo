import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { Empty } from "@/components/sf/bits"
import { Card } from "@/components/sf/card"
import { getCardExtras, searchProducts } from "@/lib/catalog"

export const metadata: Metadata = {
  title: "Search",
  robots: { index: false, follow: true }, // result pages are thin/duplicate content
}

async function Results({ searchParams }: PageProps<"/search">) {
  const sp = await searchParams
  const q = String([sp.q ?? ""].flat()[0]).trim().slice(0, 100)
  const [page, extras] = await Promise.all([q ? searchProducts(q, { limit: 24 }) : { items: [], fuzzy: false }, getCardExtras()])
  return (
    <>
      <section className="wrap page-head">
        <span className="t-label brand">SEARCH</span>
        <h1 className="t-display">{q ? `Results for “${q}”.` : "Search."}</h1>
        {page.fuzzy && <p className="t-sub">No exact matches, so here is the closest we have.</p>}
      </section>
      <section className="wrap" style={{ paddingBottom: 96 }}>
        <div className="grid-products">
          {page.items.length ? (
            page.items.map((p) => <Card key={p.id} product={p} extra={extras[p.id]} />)
          ) : (
            <Empty title={<p className="t-head">No results. The croc looked everywhere.</p>}>
              <Link className="btn" href="/shop">
                [ See everything ]
              </Link>
            </Empty>
          )}
        </div>
      </section>
    </>
  )
}

export default function SearchPage(props: PageProps<"/search">) {
  return (
    <Suspense fallback={null}>
      <Results {...props} />
    </Suspense>
  )
}
