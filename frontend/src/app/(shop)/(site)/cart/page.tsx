import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { Crumbs, Empty } from "@/components/sf/bits"
import { CartView } from "@/components/sf/cart"
import { api } from "@/lib/api/client"
import { getCurrentUser } from "@/lib/session"

export const metadata: Metadata = { title: "Cart", description: "Review your Hot Smoothie Co. cart.", robots: { index: false } }

async function Cart() {
  const [{ data: cart }, user] = await Promise.all([(await api()).GET("/api/v1/cart"), getCurrentUser()])
  if (!cart?.items.length) {
    return (
      <Empty title={<h2 className="t-display">Your cart is as empty as your wall.</h2>}>
        <p className="t-sub">Let&apos;s fix both.</p>
        <Link className="btn" href="/shop">
          [ Shop the drop ]
        </Link>
      </Empty>
    )
  }
  return <CartView cart={cart} signedIn={!!user} />
}

export default function CartPage() {
  return (
    <>
      <Crumbs items={[["Home", "/"], ["Cart"]]} />
      <section className="wrap" style={{ paddingTop: 32, paddingBottom: 96 }}>
        <h1 className="t-display" style={{ marginBottom: 40 }}>
          Your cart.
        </h1>
        <Suspense fallback={null}>
          <Cart />
        </Suspense>
      </section>
    </>
  )
}
