import type { Metadata } from "next"

import { Listing } from "@/components/shop/listing"

export const metadata: Metadata = {
  title: "Shop all posters & prints",
  description: "Every poster, art print, framed piece and sticker from The Hot Smoothie Co.",
  alternates: { canonical: "/shop" },
}

export default function ShopPage({ searchParams }: PageProps<"/shop">) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <h1 className="mb-8 font-display text-5xl leading-none tracking-tight">Shop all</h1>
      <Listing searchParams={searchParams} />
    </div>
  )
}
