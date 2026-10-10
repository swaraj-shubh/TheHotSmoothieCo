"use client"

import Link from "next/link"
import { useTransition } from "react"
import { toast } from "sonner"

import { moveWishlistToCart, removeFromWishlist } from "@/app/actions/shop"
import { ProductImage } from "@/components/shop/product-image"
import { Button } from "@/components/ui/button"
import type { WishlistItemOut } from "@/lib/api/types"
import { rupees } from "@/lib/format"

export function WishlistGrid({ items }: { items: WishlistItemOut[] }) {
  const [pending, start] = useTransition()
  return (
    <ul className="grid grid-cols-2 gap-x-4 gap-y-8 sm:grid-cols-3 lg:grid-cols-4">
      {items.map((item) => (
        <li key={item.id} className="space-y-3">
          <Link href={`/product/${item.product.slug}`}>
            <ProductImage src={item.product.thumbnail_url} alt={item.product.title} seed={item.product.slug} />
          </Link>
          <div>
            <p className="font-medium">{item.product.title}</p>
            <p className="text-sm text-muted-foreground">
              {item.variant ? `${item.variant.title} · ${rupees(item.variant.price_paise)}` : `From ${rupees(item.product.min_price_paise)}`}
            </p>
          </div>
          <div className="flex gap-2">
            {item.variant ? (
              <Button
                size="sm"
                disabled={pending || !item.variant.in_stock}
                onClick={() =>
                  start(async () => {
                    const r = await moveWishlistToCart(item.id, item.variant!.id)
                    if (r.ok) toast.success(r.message)
                    else toast.error(r.error)
                  })
                }
              >
                {item.variant.in_stock ? "Move to cart" : "Sold out"}
              </Button>
            ) : (
              <Button asChild size="sm">
                <Link href={`/product/${item.product.slug}`}>Choose size</Link>
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              disabled={pending}
              onClick={() => start(async () => void (await removeFromWishlist(item.id)))}
            >
              Remove
            </Button>
          </div>
        </li>
      ))}
    </ul>
  )
}
