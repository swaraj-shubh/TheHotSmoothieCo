import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import { Suspense } from "react"
import { BadgeCheck, Star } from "lucide-react"

import { Gallery } from "@/components/shop/gallery"
import { ProductGrid, ProductGridSkeleton } from "@/components/shop/product-card"
import { PurchasePanel } from "@/components/shop/purchase-panel"
import { ReviewForm } from "@/components/shop/review-form"
import type { ProductDetail } from "@/lib/api/types"
import { getPrerenderSlugs, getProduct, getProducts, getReviews } from "@/lib/catalog"
import { formatDate } from "@/lib/format"
import { getCurrentUser } from "@/lib/session"
import { SITE } from "@/lib/site"

export async function generateStaticParams() {
  return (await getPrerenderSlugs()).map((slug) => ({ slug }))
}

export async function generateMetadata({ params }: PageProps<"/product/[slug]">): Promise<Metadata> {
  const { slug } = await params
  const product = await getProduct(slug)
  if (!product) return { title: "Product not found" }
  const image = product.media[0]?.url
  const description = product.seo_description ?? product.short_description ?? `${product.title} — art print.`
  return {
    title: product.seo_title ?? product.title,
    description,
    alternates: { canonical: `/product/${slug}` },
    openGraph: {
      type: "website",
      title: product.title,
      description,
      url: `/product/${slug}`,
      ...(image ? { images: [{ url: image, alt: product.media[0]?.alt_text ?? product.title }] } : {}),
    },
  }
}

/** schema.org Product markup: price, availability and rating in Google results. */
function ProductJsonLd({ product }: { product: ProductDetail }) {
  const inStock = product.variants.some((v) => v.in_stock)
  const data = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.title,
    description: product.short_description ?? product.description ?? undefined,
    image: product.media.map((m) => m.url),
    sku: product.variants[0]?.sku,
    brand: { "@type": "Brand", name: SITE.name },
    url: `${SITE.url}/product/${product.slug}`,
    offers: {
      "@type": "AggregateOffer",
      priceCurrency: "INR",
      lowPrice: ((product.min_price_paise ?? 0) / 100).toFixed(2),
      highPrice: ((product.max_price_paise ?? 0) / 100).toFixed(2),
      offerCount: product.variants.length,
      availability: inStock ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
    },
    ...(product.rating_count
      ? { aggregateRating: { "@type": "AggregateRating", ratingValue: product.rating_average, reviewCount: product.rating_count } }
      : {}),
  }
  return (
    <script
      type="application/ld+json"
      // JSON.stringify output with "<" escaped so a product title can never close the script tag
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  )
}

function Stars({ value, className = "size-4" }: { value: number; className?: string }) {
  return (
    <span className="flex" aria-label={`${value.toFixed(1)} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((n) => (
        <Star key={n} aria-hidden className={`${className} ${n <= Math.round(value) ? "fill-foreground text-foreground" : "text-border"}`} />
      ))}
    </span>
  )
}

async function Reviews({ product }: { product: ProductDetail }) {
  const [{ page, summary }, user] = await Promise.all([getReviews(product.slug), getCurrentUser()])
  return (
    <section id="reviews" aria-labelledby="reviews-title" className="grid gap-10 border-t pt-20 lg:grid-cols-[320px_1fr]">
      <div className="space-y-4">
        <h2 id="reviews-title" className="font-display text-4xl">
          Reviews
        </h2>
        {summary?.count ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Stars value={summary.average ?? 0} className="size-5" />
              <span className="font-semibold">{summary.average?.toFixed(1)}</span>
              <span className="text-muted-foreground">({summary.count})</span>
            </div>
            {[5, 4, 3, 2, 1].map((star) => {
              const n = summary.distribution[star] ?? 0
              return (
                <div key={star} className="flex items-center gap-2 text-sm">
                  <span className="w-3">{star}</span>
                  <div className="h-1 flex-1 overflow-hidden bg-muted">
                    <div className="h-full bg-foreground" style={{ width: `${(n / summary.count) * 100}%` }} />
                  </div>
                  <span className="w-6 text-right text-muted-foreground">{n}</span>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-muted-foreground">No reviews yet. Be the first!</p>
        )}
        {user ? (
          <ReviewForm productId={product.id} slug={product.slug} />
        ) : (
          <p className="text-sm">
            <Link href={`/login?next=/product/${product.slug}%23reviews`} className="underline underline-offset-4">
              Sign in
            </Link>{" "}
            to write a review.
          </p>
        )}
      </div>
      <ul className="space-y-6">
        {page.items.map((r) => (
          <li key={r.id} className="border-b pb-6">
            <div className="flex items-center gap-3">
              <Stars value={r.rating} />
              {r.title && <p className="font-semibold">{r.title}</p>}
            </div>
            {r.body && <p className="mt-2 whitespace-pre-line text-sm leading-relaxed">{r.body}</p>}
            <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              {r.author} · {formatDate(r.created_at)}
              {r.verified_purchase && (
                <span className="flex items-center gap-1">
                  <BadgeCheck className="size-3.5" aria-hidden /> Verified purchase
                </span>
              )}
            </p>
          </li>
        ))}
      </ul>
    </section>
  )
}

async function Related({ product }: { product: ProductDetail }) {
  if (!product.category) return null
  const page = await getProducts({ category: product.category.slug, limit: 5 })
  const items = page.items.filter((p) => p.id !== product.id).slice(0, 4)
  if (!items.length) return null
  return (
    <section aria-labelledby="related" className="space-y-10 border-t pt-20">
      <h2 id="related" className="font-display text-4xl">
        You might also like
      </h2>
      <ProductGrid products={items} />
    </section>
  )
}

async function ProductView({ params }: { params: PageProps<"/product/[slug]">["params"] }) {
  const { slug } = await params
  const product = await getProduct(slug)
  if (!product) notFound()

  return (
    <>
      <ProductJsonLd product={product} />
      <nav aria-label="Breadcrumb" className="mb-8 text-xs text-muted-foreground">
        <Link href="/shop" className="hover:underline">
          Shop
        </Link>
        {product.category && (
          <>
            {" / "}
            <Link href={`/category/${product.category.slug}`} className="hover:underline">
              {product.category.name}
            </Link>
          </>
        )}
        {" / "}
        <span aria-current="page">{product.title}</span>
      </nav>
      <div className="grid gap-10 lg:grid-cols-[1.25fr_1fr] lg:gap-20">
        <Gallery product={product} />
        <div className="space-y-8 lg:sticky lg:top-32 lg:self-start">
          <div className="space-y-3">
            {product.category && <p className="eyebrow">{product.category.name}</p>}
            <h1 className="font-display text-5xl leading-[0.95] tracking-tight md:text-6xl">{product.title}</h1>
            {product.rating_count ? (
              <a href="#reviews" className="flex items-center gap-2 text-sm">
                <Stars value={product.rating_average ?? 0} />
                <span className="text-muted-foreground">{product.rating_count} reviews</span>
              </a>
            ) : null}
            {product.short_description && <p className="text-muted-foreground">{product.short_description}</p>}
          </div>
          <PurchasePanel product={product} />
          {product.description && (
            <div className="space-y-3 border-t pt-6">
              <h2 className="eyebrow text-foreground">About this print</h2>
              <p className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground">{product.description}</p>
            </div>
          )}
          {product.tags.length > 0 && (
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              {product.tags.map((t) => (
                <li key={t.slug}>
                  <Link href={`/search?q=${encodeURIComponent(t.name)}`} className="underline-offset-4 hover:text-foreground hover:underline">
                    {t.name}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="mt-28 space-y-24">
        <Suspense fallback={<div className="h-40 animate-pulse bg-muted" />}>
          <Reviews product={product} />
        </Suspense>
        <Suspense fallback={<ProductGridSkeleton count={4} />}>
          <Related product={product} />
        </Suspense>
      </div>
    </>
  )
}

export default function ProductPage(props: PageProps<"/product/[slug]">) {
  return (
    <div className="mx-auto max-w-7xl px-4 pt-8 sm:px-6 lg:px-8">
      <Suspense
        fallback={
          <div className="grid gap-10 lg:grid-cols-2">
            <div className="aspect-[4/5] animate-pulse bg-muted" />
            <div className="space-y-4">
              <div className="h-10 w-3/4 animate-pulse rounded bg-muted" />
              <div className="h-8 w-1/3 animate-pulse rounded bg-muted" />
              <div className="h-40 animate-pulse rounded bg-muted" />
            </div>
          </div>
        }
      >
        <ProductView params={props.params} />
      </Suspense>
    </div>
  )
}
