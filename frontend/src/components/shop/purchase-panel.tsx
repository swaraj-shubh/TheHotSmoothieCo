"use client"

import { usePathname } from "next/navigation"
import { useMemo, useState, useTransition } from "react"
import { Heart, Minus, Plus } from "lucide-react"
import { toast } from "sonner"

import { addToCart, buyNow } from "@/app/actions/cart"
import { addToWishlist } from "@/app/actions/shop"
import { Button } from "@/components/ui/button"
import type { ProductDetail } from "@/lib/api/types"
import { percentOff, rupees } from "@/lib/format"
import { cn } from "@/lib/utils"

type Selection = Record<string, string>

/** Option picker (size, frame…) -> the matching variant -> price, stock, cart actions. */
export function PurchasePanel({ product }: { product: ProductDetail }) {
  const pathname = usePathname()
  const [pending, startTransition] = useTransition()
  // Default to the first in-stock variant so the page opens on something buyable.
  const initial = product.variants.find((v) => v.in_stock) ?? product.variants[0]
  const [selection, setSelection] = useState<Selection>(initial?.attributes ?? {})
  const [quantity, setQuantity] = useState(1)

  const variant = useMemo(
    () =>
      product.variants.find((v) => product.options.every((o) => v.attributes[o.code] === selection[o.code])) ?? null,
    [product, selection],
  )

  /** Is this option value available given the other current choices? */
  function available(code: string, value: string) {
    return product.variants.some(
      (v) =>
        v.in_stock &&
        v.attributes[code] === value &&
        product.options.every((o) => o.code === code || v.attributes[o.code] === selection[o.code]),
    )
  }

  function run(fn: () => Promise<{ ok: boolean; error?: string; message?: string }>) {
    startTransition(async () => {
      const result = await fn()
      if (result.ok) {
        if (result.message) toast.success(result.message)
      } else toast.error(result.error ?? "Something went wrong")
    })
  }

  const max = variant?.max_purchasable ?? 0
  const off = variant ? percentOff(variant.price_paise, variant.compare_at_price_paise) : null

  return (
    <div className="space-y-8">
      <div className="flex items-baseline gap-3" aria-live="polite">
        {variant ? (
          <>
            <span className="text-xl tabular-nums">{rupees(variant.price_paise)}</span>
            {off && (
              <>
                <s className="text-muted-foreground tabular-nums">{rupees(variant.compare_at_price_paise)}</s>
                <span className="text-sm text-sale">−{off}%</span>
              </>
            )}
          </>
        ) : (
          <span className="text-muted-foreground">This combination isn’t available</span>
        )}
      </div>
      <p className="-mt-6 text-xs text-muted-foreground">Inclusive of all taxes. Free shipping over ₹999.</p>

      {product.options.map((option) => (
        <fieldset key={option.code}>
          <legend className="mb-3 flex gap-2 text-sm">
            <span className="eyebrow text-foreground">{option.name}</span>
            <span className="text-xs text-muted-foreground">{selection[option.code]}</span>
          </legend>
          <div className="flex flex-wrap gap-2">
            {option.values.map((value) => {
              const selected = selection[option.code] === value
              const inStock = available(option.code, value)
              return (
                <button
                  key={value}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setSelection((s) => ({ ...s, [option.code]: value }))}
                  className={cn(
                    "h-10 min-w-16 border px-4 text-sm transition-colors",
                    selected ? "border-foreground ring-1 ring-foreground" : "border-border hover:border-foreground/50",
                    !inStock && !selected && "text-muted-foreground line-through decoration-1",
                  )}
                >
                  {value}
                </button>
              )
            })}
          </div>
        </fieldset>
      ))}

      <div className="flex items-center gap-2 text-xs text-muted-foreground" aria-live="polite">
        <span
          className={cn("size-1.5 rounded-full", !variant?.in_stock ? "bg-muted-foreground" : max <= 3 ? "bg-sale" : "bg-emerald-600")}
          aria-hidden
        />
        {variant?.in_stock ? (max <= 3 ? `Only ${max} left` : "In stock · ships in 2–4 days") : "Sold out"}
      </div>

      <div className="grid grid-cols-[auto_1fr_auto] gap-3">
        <div className="flex h-12 items-center border" role="group" aria-label="Quantity">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Decrease quantity"
            disabled={quantity <= 1}
            onClick={() => setQuantity((q) => q - 1)}
          >
            <Minus />
          </Button>
          <span className="w-8 text-center tabular-nums" aria-live="polite">
            {quantity}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Increase quantity"
            disabled={quantity >= Math.max(max, 1)}
            onClick={() => setQuantity((q) => q + 1)}
          >
            <Plus />
          </Button>
        </div>
        <Button
          size="lg"
          className="h-12 text-sm tracking-wide"
          disabled={!variant?.in_stock || pending}
          onClick={() => variant && run(() => addToCart(variant.id, quantity))}
        >
          Add to cart
        </Button>
        <Button
          size="icon-lg"
          variant="outline"
          className="size-12"
          aria-label="Save to wishlist"
          disabled={pending}
          onClick={() => run(() => addToWishlist(product.id, variant?.id ?? null, pathname))}
        >
          <Heart strokeWidth={1.5} />
        </Button>
        <Button
          size="lg"
          variant="outline"
          className="col-span-3 h-12 text-sm tracking-wide"
          disabled={!variant?.in_stock || pending}
          onClick={() => variant && run(() => buyNow(variant.id, quantity))}
        >
          Buy now
        </Button>
      </div>

      {variant && (variant.length_mm || variant.weight_grams) && (
        <dl className="grid grid-cols-2 gap-y-2 border-t pt-6 text-sm">
          <dt className="text-muted-foreground">SKU</dt>
          <dd className="text-xs tracking-wide">{variant.sku}</dd>
          {variant.length_mm && variant.width_mm && (
            <>
              <dt className="text-muted-foreground">Size</dt>
              <dd>
                {variant.width_mm / 10} × {variant.length_mm / 10} cm
              </dd>
            </>
          )}
          {variant.weight_grams && (
            <>
              <dt className="text-muted-foreground">Weight</dt>
              <dd>{variant.weight_grams} g</dd>
            </>
          )}
        </dl>
      )}
    </div>
  )
}
