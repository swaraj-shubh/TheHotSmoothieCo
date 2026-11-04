import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import { Suspense } from "react"

import { Crumbs } from "@/components/sf/bits"
import { Card } from "@/components/sf/card"
import { getCardExtras, getCollection, getCollections, getProducts } from "@/lib/catalog"
import { collectionCopy } from "@/lib/content"
import { cdn } from "@/lib/format"

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
    description: collection.seo_description ?? collectionCopy(collection).tagline ?? `The ${collection.name} collection.`,
    alternates: { canonical: `/collection/${slug}` },
  }
}

async function View({ params }: { params: PageProps<"/collection/[slug]">["params"] }) {
  const { slug } = await params
  const [c, others, extras] = await Promise.all([getCollection(slug), getCollections(), getCardExtras()])
  if (!c) notFound()
  const { items } = await getProducts({ collection: slug, limit: 100 })
  const { tagline, story } = collectionCopy(c)
  return (
    <>
      <Crumbs items={[["Home", "/"], ["Collections", "/shop"], [c.name]]} />
      <section className="wrap" id="c-hero" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 64, alignItems: "center", paddingTop: 40, paddingBottom: 72 }}>
        <div style={{ display: "grid", gap: 20, justifyItems: "start" }}>
          <span className="t-label brand">COLLECTION</span>
          <h1 className="t-display">{c.name}</h1>
          <p className="t-sub">{tagline}</p>
          <p style={{ maxWidth: "56ch" }}>{story}</p>
          <a className="btn" href="#grid">
            [ Jump to the posters ]
          </a>
        </div>
        {c.image_url && <img src={cdn(c.image_url, 1400)} alt={`${c.name} posters in a living room`} style={{ width: "100%", aspectRatio: "480/542", objectFit: "cover", borderRadius: 12 }} />}
      </section>
      <section className="wrap" style={{ paddingBottom: 32, display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h2 className="t-head">The posters</h2>
        <span className="t-cap muted">
          {items.length} {items.length === 1 ? "poster" : "posters"}
        </span>
      </section>
      <section className="wrap" style={{ paddingBottom: 96 }}>
        <div className="grid-products" id="grid">
          {items.map((p) => (
            <Card key={p.id} product={p} extra={extras[p.id]} />
          ))}
        </div>
      </section>
      <section className="wrap surface section" style={{ paddingTop: 72, paddingBottom: 72 }}>
        <h2 className="t-head" style={{ marginBottom: 32 }}>
          Other worlds
        </h2>
        <div className="collections" id="others" style={{ gridTemplateColumns: "repeat(2,1fr)" }}>
          {others
            .filter((x) => x.slug !== slug)
            .map((x) => (
              <Link key={x.id} className="coll" href={`/collection/${x.slug}`}>
                <span className="coll__media">
                  {x.image_url && <img src={cdn(x.image_url, 1200)} alt="" loading="lazy" />}
                  <span className="coll__name t-head">{x.name}</span>
                </span>
              </Link>
            ))}
        </div>
      </section>
    </>
  )
}

export default function CollectionPage(props: PageProps<"/collection/[slug]">) {
  return (
    <Suspense fallback={null}>
      <View params={props.params} />
    </Suspense>
  )
}
