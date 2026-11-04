import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { Empty } from "@/components/sf/bits"
import { Card } from "@/components/sf/card"
import { api, unwrap } from "@/lib/api/client"
import { getCardExtras } from "@/lib/catalog"
import { getCurrentUser } from "@/lib/session"

export const metadata: Metadata = { title: "Wishlist", description: "Posters you saved for later.", robots: { index: false } }

async function Grid() {
  const user = await getCurrentUser()
  const items = user ? unwrap(await (await api()).GET("/api/v1/wishlist", { params: { query: { limit: 60 } } })).items : []
  const extras = await getCardExtras()
  return (
    <div className="grid-products" id="grid">
      {items.length ? (
        items.map((i) => <Card key={i.id} product={i.product} extra={extras[i.product.id]} />)
      ) : (
        <Empty title={<p className="t-head">Nothing saved. Very disciplined.</p>}>
          <p>Tap the heart on anything that made you feel personally attacked.</p>
          <Link className="btn" href="/shop">
            [ Browse the posters ]
          </Link>
        </Empty>
      )}
    </div>
  )
}

export default function WishlistPage() {
  return (
    <>
      <section className="wrap page-head">
        <span className="t-label brand">SAVED FOR LATER</span>
        <h1 className="t-display">Your wishlist.</h1>
        <p className="t-sub">Things that made you feel personally attacked.</p>
      </section>
      <section className="wrap" style={{ paddingBottom: 96 }}>
        <Suspense fallback={null}>
          <Grid />
        </Suspense>
      </section>
    </>
  )
}
