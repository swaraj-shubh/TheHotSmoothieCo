import Image from "next/image"
import Link from "next/link"
import { ArrowRight, ArrowUpRight } from "lucide-react"

import { ProductGrid } from "@/components/shop/product-card"
import { ProductImage } from "@/components/shop/product-image"
import { Button } from "@/components/ui/button"
import { getBanners, getCategories, getCollections, getProducts } from "@/lib/catalog"

function SectionHead({ eyebrow, title, href, linkLabel }: { eyebrow: string; title: string; href: string; linkLabel: string }) {
  return (
    <div className="mb-10 flex items-end justify-between gap-6">
      <div className="space-y-3">
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="font-display text-4xl leading-none md:text-5xl">{title}</h2>
      </div>
      <Link href={href} className="group flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground">
        {linkLabel}
        <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
      </Link>
    </div>
  )
}

export default async function HomePage() {
  const [banners, categories, collections, newest] = await Promise.all([
    getBanners("HOME_HERO"),
    getCategories(),
    getCollections(),
    getProducts({ sort: "newest", limit: 8 }),
  ])
  const hero = banners[0]
  const featured = collections[0]
  const featuredProducts = featured ? await getProducts({ collection: featured.slug, limit: 4 }) : null
  const heroProduct = featuredProducts?.items[0] ?? newest.items[0]

  return (
    <>
      <section className="mx-auto grid max-w-7xl items-center gap-12 px-4 pt-12 pb-20 sm:px-6 md:grid-cols-[1fr_1.1fr] md:gap-16 md:pt-20 lg:px-8">
        <div className="space-y-8">
          <p className="eyebrow">Designed in India · Printed to last</p>
          <h1 className="font-display text-[3.25rem] leading-[0.95] tracking-tight md:text-7xl lg:text-[5.5rem]">
            {hero?.title ?? (
              <>
                Art for walls
                <br />
                worth <em>looking at.</em>
              </>
            )}
          </h1>
          <p className="max-w-sm text-base leading-relaxed text-muted-foreground">
            {hero?.subtitle ?? "Posters, prints and stickers on 250 gsm archival paper. Delivered rolled, or framed and ready to hang."}
          </p>
          <div className="flex flex-wrap items-center gap-6">
            <Button asChild size="lg" className="h-12 px-8 text-sm tracking-wide">
              <Link href={hero?.link_url ?? "/shop"}>Shop all prints</Link>
            </Button>
            <Link href="/search?q=framed" className="text-sm underline decoration-foreground/30 underline-offset-[6px] transition hover:decoration-foreground">
              Framed prints
            </Link>
          </div>
        </div>
        {hero?.image_url ? (
          <div className="relative aspect-[4/5] overflow-hidden bg-muted">
            <Image src={hero.image_url} alt="" fill priority className="object-cover" sizes="(min-width: 768px) 50vw, 100vw" />
          </div>
        ) : heroProduct ? (
          <Link href={`/product/${heroProduct.slug}`} className="group block" aria-label={heroProduct.title}>
            <ProductImage
              src={heroProduct.image_url}
              alt={heroProduct.title}
              seed={heroProduct.slug}
              priority
              sizes="(min-width: 768px) 50vw, 100vw"
            />
            <p className="mt-3 flex justify-between text-xs text-muted-foreground">
              <span>{heroProduct.title}</span>
              <span className="flex items-center gap-1 group-hover:text-foreground">
                View print <ArrowUpRight className="size-3" aria-hidden />
              </span>
            </p>
          </Link>
        ) : null}
      </section>

      <section className="border-y">
        <ul className="mx-auto grid max-w-7xl divide-y px-4 text-sm sm:grid-cols-3 sm:divide-x sm:divide-y-0 sm:px-6 lg:px-8">
          {[
            ["Archival paper", "250 gsm, fade-resistant inks"],
            ["Framed or rolled", "Black, white and oak frames"],
            ["Free shipping", "On every order over ₹999"],
          ].map(([title, body]) => (
            <li key={title} className="py-6 sm:px-8 sm:first:pl-0 sm:last:pr-0">
              <p className="font-medium">{title}</p>
              <p className="text-muted-foreground">{body}</p>
            </li>
          ))}
        </ul>
      </section>

      {featured && featuredProducts && featuredProducts.items.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pt-24 sm:px-6 lg:px-8" aria-label={featured.name}>
          <SectionHead eyebrow="Collection" title={featured.name} href={`/collection/${featured.slug}`} linkLabel="View collection" />
          <ProductGrid products={featuredProducts.items} />
        </section>
      )}

      {categories.length > 0 && (
        <section className="mx-auto max-w-7xl px-4 pt-28 sm:px-6 lg:px-8" aria-labelledby="cats">
          <p className="eyebrow mb-6" id="cats">
            Browse
          </p>
          <ul className="border-t">
            {categories.map((c, i) => (
              <li key={c.id} className="border-b">
                <Link href={`/category/${c.slug}`} className="group flex items-baseline gap-6 py-6 md:py-8">
                  <span className="w-8 text-xs text-muted-foreground tabular-nums">{String(i + 1).padStart(2, "0")}</span>
                  <span className="font-display text-4xl leading-none transition-transform duration-300 group-hover:translate-x-2 md:text-6xl">
                    {c.name}
                  </span>
                  <ArrowRight className="ml-auto size-5 self-center text-muted-foreground transition group-hover:text-foreground" strokeWidth={1.5} aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mx-auto max-w-7xl px-4 pt-28 sm:px-6 lg:px-8" aria-label="New arrivals">
        <SectionHead eyebrow="Just in" title="New arrivals" href="/shop" linkLabel="Shop all" />
        {newest.items.length ? (
          <ProductGrid products={newest.items} />
        ) : (
          <p className="text-muted-foreground">New prints are on their way.</p>
        )}
      </section>

      <section className="mx-auto max-w-3xl px-4 pt-32 text-center sm:px-6">
        <p className="eyebrow mb-6">The studio</p>
        <p className="font-display text-3xl leading-tight md:text-5xl">
          Designed in India, printed on archival paper, and made to <em>stay on your wall</em> for years.
        </p>
      </section>
    </>
  )
}
