import Link from "next/link"

import type { ProductCard } from "@/lib/api/types"
import type { CardExtra } from "@/lib/catalog"
import { cdn, money } from "@/lib/format"

import { QuickAdd } from "./add-button"
import { WishHeart } from "./wish"

export function Card({ product: p, extra }: { product: ProductCard; extra?: CardExtra }) {
  const href = `/product/${p.slug}`
  const chip = p.in_stock ? extra?.chip : "Sold out"
  return (
    <article className="card">
      <Link className="card__media" href={href} aria-label={p.title}>
        <img src={p.image_url ? cdn(p.image_url, 900) : "/assets/croc-wordmark.png"} alt={p.image_alt ?? `${p.title} poster`} loading="lazy" />
      </Link>
      {chip && <span className="chip">{chip}</span>}
      <WishHeart productId={p.id} title={p.title} />
      <div className="card__meta">
        <span className="t-cap muted">{extra?.collection}</span>
        <Link className="card__title" href={href}>
          {p.title}
        </Link>
      </div>
      <div className="card__row">
        <span className="t-price">From {money(p.min_price_paise)}</span>
        <QuickAdd slug={p.slug} title={p.title} inStock={p.in_stock} />
      </div>
    </article>
  )
}
