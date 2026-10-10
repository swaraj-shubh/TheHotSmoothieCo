import Link from "next/link"
import { Star } from "lucide-react"

import type { ProductCard as Card } from "@/lib/api/types"
import { percentOff, rupees } from "@/lib/format"

import { ProductImage } from "./product-image"

export function Price({
  price,
  maxPrice,
  compareAt,
  className = "",
}: {
  price: number | null | undefined
  maxPrice?: number | null
  compareAt?: number | null
  className?: string
}) {
  if (price == null) return null
  const off = percentOff(price, compareAt)
  return (
    <p className={`flex flex-wrap items-baseline gap-x-2 tabular-nums ${className}`}>
      <span>{maxPrice && maxPrice !== price ? `From ${rupees(price)}` : rupees(price)}</span>
      {off && (
        <>
          <s className="text-muted-foreground">{rupees(compareAt)}</s>
          <span className="text-sale">−{off}%</span>
        </>
      )}
    </p>
  )
}

export function ProductCardView({ product, priority }: { product: Card; priority?: boolean }) {
  const onSale = product.in_stock && percentOff(product.min_price_paise ?? 0, product.max_compare_at_price_paise)
  return (
    <Link href={`/product/${product.slug}`} prefetch className="group block" aria-label={product.title}>
      <div className="relative">
        <ProductImage
          src={product.thumbnail_url ?? product.image_url}
          alt={product.image_alt ?? product.title}
          seed={product.slug}
          priority={priority}
        />
        {(!product.in_stock || onSale) && (
          <span className="eyebrow absolute top-3 left-3 text-foreground">{product.in_stock ? "Sale" : "Sold out"}</span>
        )}
      </div>
      <div className="mt-4 space-y-1 text-sm">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="line-clamp-1 font-medium">{product.title}</h3>
          {product.rating_count ? (
            <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
              <Star className="size-3 fill-current" aria-hidden />
              {product.rating_average?.toFixed(1)}
              <span className="sr-only">out of 5 from {product.rating_count} reviews</span>
            </span>
          ) : null}
        </div>
        <Price price={product.min_price_paise} maxPrice={product.max_price_paise} className="text-muted-foreground" />
      </div>
    </Link>
  )
}

export function ProductGrid({ products, priorityCount = 0 }: { products: Card[]; priorityCount?: number }) {
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-12 sm:gap-x-6 lg:grid-cols-4">
      {products.map((p, i) => (
        <li key={p.id}>
          <ProductCardView product={p} priority={i < priorityCount} />
        </li>
      ))}
    </ul>
  )
}

export function ProductGridSkeleton({ count = 8 }: { count?: number }) {
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-12 sm:gap-x-6 lg:grid-cols-4" aria-busy>
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="space-y-3">
          <div className="aspect-[4/5] animate-pulse bg-muted" />
          <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
          <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
        </li>
      ))}
    </ul>
  )
}
