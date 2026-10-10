import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { Suspense } from "react"

import { CheckoutFlow } from "@/components/shop/checkout-flow"
import { api, unwrap } from "@/lib/api/client"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Checkout", robots: { index: false } }

async function Checkout() {
  await requireUser("/checkout")
  const client = await api()
  const [cart, addresses] = await Promise.all([
    client.GET("/api/v1/cart").then(unwrap),
    client.GET("/api/v1/users/me/addresses").then(unwrap),
  ])
  if (!cart.items.length) redirect("/cart")
  return <CheckoutFlow cart={cart} addresses={addresses} />
}

export default function CheckoutPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-8 font-display text-5xl leading-none tracking-tight">Checkout</h1>
      <Suspense fallback={<div className="h-96 animate-pulse bg-muted" />}>
        <Checkout />
      </Suspense>
    </div>
  )
}
