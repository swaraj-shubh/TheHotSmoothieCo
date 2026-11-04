import type { Metadata } from "next"
import { notFound } from "next/navigation"
import { Suspense } from "react"

import { Crumbs } from "@/components/sf/bits"
import { Card } from "@/components/sf/card"
import { Pdp } from "@/components/sf/pdp"
import type { ProductDetail } from "@/lib/api/types"
import { getCardExtras, getPrerenderSlugs, getProduct, getProducts, getReviews } from "@/lib/catalog"
import { formatDate } from "@/lib/format"
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

/** Real customer reviews, in the design's review cards. Not in the design's product page, so the
 *  section only appears once a product has approved reviews. */
async function Reviews({ product }: { product: ProductDetail }) {
  const { page, summary } = await getReviews(product.slug)
  if (!summary?.count) return null
  return (
    <section className="wrap section" id="reviews" style={{ paddingTop: 96, paddingBottom: 0 }}>
      <h2 className="t-display">
        {summary.average?.toFixed(1)} out of 5. {summary.count} {summary.count === 1 ? "opinion" : "opinions"}.
      </h2>
      <div className="reviews">
        {page.items.map((r) => (
          <figure key={r.id} className="review" style={{ margin: 0 }}>
            <div className="stars" aria-label={`${r.rating} out of 5 stars`}>
              {"★".repeat(r.rating)}
            </div>
            <blockquote className="t-sub" style={{ margin: 0 }}>
              {r.title && <b>{r.title} </b>}
              {r.body}
            </blockquote>
            <figcaption className="t-cap muted">
              {r.author} · {formatDate(r.created_at)}
              {r.verified_purchase && " · Verified purchase"}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  )
}

async function Related({ product }: { product: ProductDetail }) {
  const [page, extras] = await Promise.all([getProducts({ limit: 4 }), getCardExtras()])
  const items = page.items.filter((p) => p.id !== product.id).slice(0, 3)
  return (
    <section className="wrap section" style={{ paddingTop: 96 }}>
      <h2 className="t-display" style={{ marginBottom: 40 }}>
        Other walls need these too.
      </h2>
      <div className="grid-products" id="related" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
        {items.map((p) => (
          <Card key={p.id} product={p} extra={extras[p.id]} />
        ))}
      </div>
    </section>
  )
}

async function ProductView({ params }: { params: PageProps<"/product/[slug]">["params"] }) {
  const { slug } = await params
  const product = await getProduct(slug)
  if (!product) notFound()
  const collection = product.collections[0]
  return (
    <>
      <ProductJsonLd product={product} />
      <Crumbs items={[["Home", "/"], ["Collections", "/shop"], ...(collection ? [[collection.name, `/collection/${collection.slug}`] as [string, string]] : []), [product.title]]} />
      <section className="wrap">
        <div className="pdp">
          <Pdp product={product} />
        </div>
      </section>
      <Suspense fallback={null}>
        <Reviews product={product} />
      </Suspense>
      <Suspense fallback={null}>
        <Related product={product} />
      </Suspense>
    </>
  )
}

export default function ProductPage(props: PageProps<"/product/[slug]">) {
  return (
    <Suspense fallback={null}>
      <ProductView params={props.params} />
    </Suspense>
  )
}
