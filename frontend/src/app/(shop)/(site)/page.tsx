import Link from "next/link"
import { Suspense } from "react"

import { QuickAdd } from "@/components/sf/add-button"
import { FaqList, Steps } from "@/components/sf/bits"
import { Card } from "@/components/sf/card"
import { ClubForm, DropTimer, VinylPlayer, WallSection } from "@/components/sf/home"
import { getBanners, getCardExtras, getCollections, getProduct, getProducts } from "@/lib/catalog"
import { CROC_PICK_SLUG, WALL_PRODUCT_SLUG } from "@/lib/content"
import { cdn, money } from "@/lib/format"

const HERO = { image: "/assets/hero.png", title: "Good taste is overrated.", href: "/shop" }

/** The hero is the design's unless staff schedule a HOME_HERO banner in the admin. */
async function Hero() {
  const banner = (await getBanners("HOME_HERO"))[0]
  return (
    <HeroView
      image={banner?.image_url ? cdn(banner.image_url, 2400) : HERO.image}
      title={banner?.title ?? HERO.title}
      href={banner?.link_url ?? HERO.href}
    />
  )
}

function HeroView({ image, title, href }: { image: string; title: string; href: string }) {
  return (
    <section className="hero" aria-labelledby="hero-h">
      <img className="hero__img" src={image} alt="" />
      <div className="hero__copy">
        <h1 className="t-hero" id="hero-h">
          {title}
        </h1>
        <Link className="btn" href={href}>
          [ Shop the drop ]
        </Link>
      </div>
    </section>
  )
}

async function Collections() {
  const collections = (await getCollections()).slice(0, 3)
  return (
    <div className="collections">
      {collections.map((c) => (
        <div key={c.id} className="coll">
          <Link className="coll__media" href={`/collection/${c.slug}`}>
            {c.image_url && <img src={cdn(c.image_url, 1200)} alt={`${c.name} poster`} loading="lazy" />}
            <span className="coll__name t-head">{c.name}</span>
          </Link>
          <Link className="btn-link" href={`/collection/${c.slug}`}>
            View collection <span aria-hidden="true">→</span>
          </Link>
        </div>
      ))}
    </div>
  )
}

async function LowestSellers() {
  const [page, extras] = await Promise.all([getProducts({ limit: 3 }), getCardExtras()])
  return (
    <div className="grid-products" id="bestsellers" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
      {page.items.map((p) => (
        <Card key={p.id} product={p} extra={extras[p.id]} />
      ))}
    </div>
  )
}

async function Wall() {
  const product = (await getProduct(WALL_PRODUCT_SLUG)) ?? (await getProducts({ limit: 1 }).then((p) => (p.items[0] ? getProduct(p.items[0].slug) : null)))
  const image = product?.media[0]?.url
  return (
    <WallSection
      posterUrl={image ? cdn(image, 700) : "/assets/poster-soul-punk.png"}
      productHref={product ? `/product/${product.slug}` : "/shop"}
      title={product?.title ?? "Soul Punk"}
    />
  )
}

async function CrocsPick() {
  const p = await getProduct(CROC_PICK_SLUG)
  if (!p) return null
  return (
    <section className="section wrap" aria-label="Croc's pick" style={{ paddingTop: 0 }}>
      <div className="pick">
        <div className="pick__croc">
          <img src="/assets/croc-wordmark.png" alt="" />
        </div>
        <div style={{ display: "grid", gap: 18, justifyItems: "start" }}>
          <span className="t-label">CROC&apos;S PICK THIS WEEK</span>
          <h2 className="t-head">{p.title}</h2>
          <p>{p.short_description}</p>
          <div style={{ display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
            <span className="t-price">{money(p.min_price_paise)}</span>
            <QuickAdd slug={p.slug} title={p.title} inStock={p.variants.some((v) => v.in_stock)} style={{ "--tag-hole": "var(--soft)" } as React.CSSProperties} />
          </div>
        </div>
        {p.media[0] && <img className="pick__poster" src={cdn(p.media[0].url, 700)} alt={`${p.title} poster`} />}
        <span className="croc-badge">Croc approved</span>
      </div>
    </section>
  )
}

const REVIEWS = [
  "“Guests now ask about the wall before the wifi password.”",
  "“It started an argument at dinner. Ten out of ten, would hang again.”",
  "“Finally, a wall with more opinions than my family group chat.”",
]

export default function HomePage() {
  return (
    <>
      <Suspense fallback={<HeroView {...HERO} />}>
        <Hero />
      </Suspense>

      <section className="drop-bar" aria-label="Next drop">
        <div className="drop-bar__left">
          <span className="chip">DROP 002</span>
          <span className="t-sub">Lands in</span>
          <DropTimer />
        </div>
        <a className="btn btn--spark" href="#club">
          [ Get notified ]
        </a>
      </section>

      <section className="section wrap statement">
        <h2 className="t-display">Hot smoothie? A poster company? What are we talking about?</h2>
        <div className="statement__body t-head">
          <p>Some people decorate to match the sofa.</p>
          <p>Some choose art because it goes with the curtains.</p>
          <p>And some people have an entire personality built around a fictional character, a questionable race strategy, or a family WhatsApp argument that happened three years ago.</p>
          <p>We make posters for the third kind.</p>
          <p className="brand">Welcome to The Hot Smoothie Co.</p>
        </div>
        <img src="/assets/divider-ornament.svg" alt="" width="234" height="39" />
      </section>

      <section className="section wrap tint" aria-labelledby="coll-h" style={{ paddingTop: 0 }}>
        <p className="t-sub" id="coll-h" style={{ maxWidth: 430, marginBottom: 40 }}>
          Meet the first residents of your walls.
          <br />
          <span className="t-cap muted" style={{ display: "block", marginTop: 8 }}>
            Three worlds. An unreasonable amount of personality.
          </span>
        </p>
        <Suspense fallback={<div className="collections" />}>
          <Collections />
        </Suspense>
      </section>

      <section className="section wrap" aria-labelledby="ls-h" style={{ paddingTop: 0 }}>
        <h2 className="t-display" id="ls-h">
          Lowest Sellers
        </h2>
        <p className="t-sub" style={{ margin: "16px 0 40px" }}>
          Because no two fingers can match.
        </p>
        <Suspense fallback={<div className="grid-products" id="bestsellers" />}>
          <LowestSellers />
        </Suspense>
      </section>

      <section className="section wrap" aria-labelledby="wall-h" style={{ paddingTop: 0 }}>
        <Suspense fallback={null}>
          <Wall />
        </Suspense>
      </section>

      <section className="section wrap" aria-labelledby="usp-h" style={{ paddingTop: 0 }}>
        <h2 className="t-display" id="usp-h" style={{ textAlign: "center", marginBottom: 56 }}>
          Just personality?
        </h2>
        <div className="usp-grid">
          {["4-5 Days Delivery", "300 GSM Glossy Sheets", "Tamper-proof Packaging", "Easy Returns", "Limited Editions per Design"].map((text, i) => (
            <div key={text} className="usp">
              <span className="t-label brand">0{i + 1}</span>
              <p className="t-sub">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section wrap dark" aria-labelledby="made-h" style={{ paddingTop: 120, paddingBottom: 120 }}>
        <h2 className="t-display" id="made-h" style={{ color: "var(--linen)" }}>
          How it&apos;s made.
        </h2>
        <p className="t-sub" style={{ marginTop: 16 }}>
          From idea to wall, without cutting corners.
        </p>
        <Steps />
      </section>

      <section className="section wrap" aria-labelledby="rev-h">
        <h2 className="t-display" id="rev-h">
          Reviewed by people with questionable taste.
        </h2>
        <div className="reviews">
          {REVIEWS.map((quote) => (
            <figure key={quote} className="review" style={{ margin: 0 }}>
              <div className="stars" aria-label="5 out of 5 stars">
                ★★★★★
              </div>
              <blockquote className="t-sub" style={{ margin: 0 }}>
                {quote}
              </blockquote>
              <figcaption className="t-cap muted">Customer name · City</figcaption>
            </figure>
          ))}
        </div>
      </section>

      <section className="section wrap" aria-label="Vinyl player" style={{ paddingTop: 0 }}>
        <div className="vinyl-split">
          <VinylPlayer />
          <div style={{ display: "grid", gap: 24, maxWidth: 706 }}>
            <h2 className="t-display">Not picked to match your cushions.</h2>
            <p className="t-head">Picked because you saw it, felt personally attacked, and immediately knew where it belonged.</p>
          </div>
        </div>
      </section>

      <section className="section wrap" aria-label="Behind the drop" style={{ paddingTop: 0 }}>
        <div className="split">
          <img className="rounded" src="/assets/croc-duo.png" alt="Two crocs plotting something" loading="lazy" />
          <div className="split__copy">
            <span className="t-label brand">BEHIND DROP 001</span>
            <h2 className="t-display">Not good taste. Good stories.</h2>
            <p className="t-sub">Drop-wise releases give each collection its own identity. They build anticipation, make the store feel like a discovery, and give you a reason to come back.</p>
            <Link className="btn-link" href="/about">
              Read the drop notes <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
      </section>

      <Suspense fallback={null}>
        <CrocsPick />
      </Suspense>

      <section className="section wrap" aria-label="Gift cards" style={{ paddingTop: 0 }}>
        <div className="gift">
          <div style={{ display: "grid", gap: 18, maxWidth: 900 }}>
            <span className="t-label" style={{ opacity: 0.85 }}>
              GIFT CARDS
            </span>
            <h2 className="t-display">For the friend who&apos;d argue about it.</h2>
            <p className="t-sub">Digital gift cards, delivered by email. They pick the obsession.</p>
          </div>
          <Link className="ticket-btn ticket-btn--ink" href="/gift-cards">
            Send a gift card
          </Link>
        </div>
      </section>

      <section className="section wrap" id="club" aria-label="Smoothie Club" style={{ paddingTop: 0 }}>
        <div className="pass-wrap">
          <img className="pass-croc" src="/assets/croc-mascot.png" alt="" loading="lazy" />
          <div className="pass">
            <div className="pass__main">
              <div className="pass__logo">
                <img src="/assets/croc-wordmark.png" alt="" />
              </div>
              <div>
                <p className="t-cap">SMOOTHIE CLUB · MEMBER PASS</p>
                <h2 className="t-head" style={{ fontSize: 44, margin: "6px 0 14px" }}>
                  First dibs on every drop.
                </h2>
                <p className="t-cap" style={{ maxWidth: 520, opacity: 0.85 }}>
                  Join 18,000 wall-obsessives. Early access, members-only prints, zero spam.
                </p>
                <ClubForm />
              </div>
            </div>
            <div className="pass__stub">
              <span className="t-label" style={{ opacity: 0.8 }}>
                YOUR WELCOME GIFT
              </span>
              <span className="t-display" style={{ color: "var(--ink)", fontSize: 72 }}>
                10%
              </span>
              <span style={{ opacity: 0.85 }}>off your first order</span>
              <img src="/assets/barcode.svg" alt="" width="142" height="36" style={{ marginTop: 16 }} />
              <span className="t-cap" style={{ opacity: 0.8 }}>
                HSC · 000214
              </span>
            </div>
            <span className="stamp">
              <span>Members only</span>
            </span>
          </div>
        </div>
      </section>

      <section className="section wrap" aria-labelledby="faq-h" style={{ paddingTop: 0 }}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,480px) 1fr", gap: 80 }} className="faq-split">
          <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
            <h2 className="t-display" id="faq-h">
              Questions, answered.
            </h2>
            <p className="t-sub">
              Still stuck? Write to us from the{" "}
              <Link href="/contact" className="brand" style={{ textDecoration: "underline" }}>
                Contact page
              </Link>
              .
            </p>
            <Link className="btn-link" href="/faq" style={{ width: "fit-content", marginTop: 8 }}>
              All questions <span aria-hidden="true">→</span>
            </Link>
          </div>
          <div id="home-faq">
            <FaqList />
          </div>
        </div>
      </section>
    </>
  )
}
