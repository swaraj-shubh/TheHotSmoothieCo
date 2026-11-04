import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { Suspense } from "react"

import { Crumbs } from "@/components/sf/bits"
import { CheckoutFlow } from "@/components/sf/checkout"
import { api, unwrap } from "@/lib/api/client"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Checkout", robots: { index: false } }

async function Checkout() {
  const user = await requireUser("/checkout")
  const client = await api()
  const [cart, addresses] = await Promise.all([
    client.GET("/api/v1/cart").then(unwrap),
    client.GET("/api/v1/users/me/addresses").then(unwrap),
  ])
  if (!cart.items.length) redirect("/cart")
  return <CheckoutFlow cart={cart} addresses={addresses} email={user.email} />
}

export default function CheckoutPage() {
  return (
    <>
      <Crumbs items={[["Home", "/"], ["Cart", "/cart"], ["Checkout"]]} />
      <section className="wrap" style={{ paddingTop: 32, paddingBottom: 96 }}>
        <h1 className="t-display" style={{ marginBottom: 48 }}>
          Almost on your wall.
        </h1>
        <Suspense fallback={null}>
          <Checkout />
        </Suspense>
      </section>
    </>
  )
}
