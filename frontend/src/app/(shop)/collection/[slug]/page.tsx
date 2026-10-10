import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { Suspense } from "react"

import { Listing } from "@/components/shop/listing"
import { getCollection, getCollections } from "@/lib/catalog"

export async function generateStaticParams() {
  const collections = await getCollections()
  return collections.length ? collections.map((c) => ({ slug: c.slug })) : [{ slug: "__placeholder__" }]
}

export async function generateMetadata({ params }: PageProps<"/collection/[slug]">): Promise<Metadata> {
  const { slug } = await params
  const collection = await getCollection(slug)
  if (!collection) return {}
  return {
    title: collection.seo_title ?? collection.name,
    description: collection.seo_description ?? collection.description ?? `The ${collection.name} collection.`,
    alternates: { canonical: `/collection/${slug}` },
  }
}

async function Heading({ params }: { params: PageProps<"/collection/[slug]">["params"] }) {
  const { slug } = await params
  const collection = await getCollection(slug)
  if (!collection) notFound()
  return (
    <div className="mb-8 space-y-2">
      <p className="eyebrow">Collection</p>
      <h1 className="font-display text-5xl leading-none tracking-tight">{collection.name}</h1>
      {collection.description && <p className="max-w-2xl text-muted-foreground">{collection.description}</p>}
    </div>
  )
}

async function CollectionListing(props: PageProps<"/collection/[slug]">) {
  const { slug } = await props.params
  return <Listing searchParams={props.searchParams} base={{ collection: slug }} />
}

export default function CollectionPage(props: PageProps<"/collection/[slug]">) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <Suspense fallback={<div className="mb-8 h-20 animate-pulse rounded bg-muted" />}>
        <Heading params={props.params} />
      </Suspense>
      <Suspense>
        <CollectionListing {...props} />
      </Suspense>
    </div>
  )
}
