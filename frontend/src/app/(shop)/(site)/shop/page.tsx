import type { Metadata } from "next"
import { Suspense } from "react"

import { Crumbs } from "@/components/sf/bits"
import { ShopGrid } from "@/components/sf/shop-grid"
import { getAllProducts, getCardExtras, getCollections } from "@/lib/catalog"

export const metadata: Metadata = {
  title: "Shop",
  description: "Every poster from The Hot Smoothie Co. 300 GSM glossy, limited editions, zero good taste required.",
  alternates: { canonical: "/shop" },
}

async function Grid() {
  const [products, extras, collections] = await Promise.all([getAllProducts(), getCardExtras(), getCollections()])
  return <ShopGrid products={products} extras={extras} collections={collections} />
}

export default function ShopPage() {
  return (
    <>
      <Crumbs items={[["Home", "/"], ["Collections"]]} />
      <section className="wrap page-head">
        <span className="t-label brand">THE WHOLE LINE-UP</span>
        <h1 className="t-display">Every poster. Zero good taste required.</h1>
        <p className="t-sub">Pick a world, or pick them all. Your walls will not file a complaint.</p>
      </section>
      <Suspense fallback={null}>
        <Grid />
      </Suspense>
    </>
  )
}
