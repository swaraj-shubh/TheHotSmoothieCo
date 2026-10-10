import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { WishlistGrid } from "@/components/account/wishlist-grid"
import { Button } from "@/components/ui/button"
import { api, unwrap } from "@/lib/api/client"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Wishlist", robots: { index: false } }

async function Wishlist() {
  await requireUser("/wishlist")
  const page = unwrap(await (await api()).GET("/api/v1/wishlist", { params: { query: { limit: 60 } } }))
  if (!page.items.length) {
    return (
      <div className=" border border-dashed py-16 text-center">
        <p className="font-display text-3xl">Nothing saved yet</p>
        <p className="mt-2 text-muted-foreground">Tap the heart on any print to keep it here.</p>
        <Button asChild className="mt-6">
          <Link href="/shop">Browse prints</Link>
        </Button>
      </div>
    )
  }
  return <WishlistGrid items={page.items} />
}

export default function WishlistPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <h1 className="mb-8 font-display text-5xl leading-none tracking-tight">Wishlist</h1>
      <Suspense fallback={<div className="h-64 animate-pulse bg-muted" />}>
        <Wishlist />
      </Suspense>
    </div>
  )
}
