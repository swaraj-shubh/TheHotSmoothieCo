import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { CartView } from "@/components/shop/cart-view"
import { Button } from "@/components/ui/button"
import { api } from "@/lib/api/client"
import { getCurrentUser } from "@/lib/session"

export const metadata: Metadata = { title: "Your cart", robots: { index: false } }

async function Cart() {
  const [{ data: cart }, user] = await Promise.all([(await api()).GET("/api/v1/cart"), getCurrentUser()])
  if (!cart?.items.length) {
    return (
      <div className=" border border-dashed py-20 text-center">
        <p className="font-display text-3xl">Your cart is empty</p>
        <p className="mt-2 text-muted-foreground">Your walls are waiting.</p>
        <Button asChild className="mt-6">
          <Link href="/shop">Start shopping</Link>
        </Button>
      </div>
    )
  }
  return <CartView cart={cart} signedIn={!!user} />
}

export default function CartPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="mb-8 font-display text-5xl leading-none tracking-tight">Your cart</h1>
      <Suspense fallback={<div className="h-64 animate-pulse bg-muted" />}>
        <Cart />
      </Suspense>
    </div>
  )
}
