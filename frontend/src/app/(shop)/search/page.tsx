import type { Metadata } from "next"
import { Suspense } from "react"

import { Listing } from "@/components/shop/listing"

export const metadata: Metadata = {
  title: "Search",
  robots: { index: false, follow: true }, // result pages are thin/duplicate content
}

async function SearchResults({ searchParams }: PageProps<"/search">) {
  const sp = await searchParams
  const q = String([sp.q ?? ""].flat()[0]).trim().slice(0, 100)
  return (
    <>
      <h1 className="mb-8 font-display text-5xl leading-none tracking-tight">{q ? <>Results for “{q}”</> : "Search"}</h1>
      {q ? (
        <Listing searchParams={searchParams} q={q} />
      ) : (
        <p className="text-muted-foreground">Type something in the search box to find posters, prints and stickers.</p>
      )}
    </>
  )
}

export default function SearchPage(props: PageProps<"/search">) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <Suspense fallback={<div className="h-10 w-64 animate-pulse rounded bg-muted" />}>
        <SearchResults {...props} />
      </Suspense>
    </div>
  )
}
