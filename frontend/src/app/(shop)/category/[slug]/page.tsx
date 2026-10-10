import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import { Suspense } from "react"

import { Listing } from "@/components/shop/listing"
import { getCategories, getCategory } from "@/lib/catalog"

export async function generateStaticParams() {
  const categories = await getCategories()
  return categories.length ? categories.map((c) => ({ slug: c.slug })) : [{ slug: "__placeholder__" }]
}

export async function generateMetadata({ params }: PageProps<"/category/[slug]">): Promise<Metadata> {
  const { slug } = await params
  const category = await getCategory(slug)
  if (!category) return {}
  return {
    title: category.seo_title ?? `${category.name} posters & prints`,
    description: category.seo_description ?? category.description ?? `Shop ${category.name} at The Hot Smoothie Co.`,
    alternates: { canonical: `/category/${slug}` },
    openGraph: { title: category.name, url: `/category/${slug}` },
  }
}

async function Heading({ params }: { params: PageProps<"/category/[slug]">["params"] }) {
  const { slug } = await params
  const category = await getCategory(slug)
  if (!category) notFound()
  return (
    <div className="mb-8 space-y-2">
      <nav aria-label="Breadcrumb" className="text-sm text-muted-foreground">
        <Link href="/shop" className="hover:underline">
          Shop
        </Link>{" "}
        / <span aria-current="page">{category.name}</span>
      </nav>
      <h1 className="font-display text-5xl leading-none tracking-tight">{category.name}</h1>
      {category.description && <p className="max-w-2xl text-muted-foreground">{category.description}</p>}
      {category.children.length > 0 && (
        <ul className="flex flex-wrap gap-2 pt-2">
          {category.children.map((c) => (
            <li key={c.id}>
              <Link href={`/category/${c.slug}`} className="rounded-full border px-3 py-1 text-sm hover:bg-muted">
                {c.name}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

async function CategoryListing(props: PageProps<"/category/[slug]">) {
  const { slug } = await props.params
  return <Listing searchParams={props.searchParams} base={{ category: slug }} />
}

export default function CategoryPage(props: PageProps<"/category/[slug]">) {
  return (
    <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
      <Suspense fallback={<div className="mb-8 h-20 animate-pulse rounded bg-muted" />}>
        <Heading params={props.params} />
      </Suspense>
      <Suspense>
        <CategoryListing {...props} />
      </Suspense>
    </div>
  )
}
