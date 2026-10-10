"use client"

import Link from "next/link"
import { useActionState, useTransition } from "react"
import { Minus, Plus, Trash2, X } from "lucide-react"
import { toast } from "sonner"

import { applyCoupon, removeCartItem, removeCoupon, updateCartItem } from "@/app/actions/cart"
import { FormMessage, SubmitButton } from "@/components/forms"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { CartOut } from "@/lib/api/types"
import { rupees } from "@/lib/format"

import { ProductImage } from "./product-image"

export function TotalsTable({ totals, couponCode }: { totals: CartOut["totals"]; couponCode?: string | null }) {
  return (
    <dl className="space-y-2 text-sm">
      <div className="flex justify-between">
        <dt>Subtotal</dt>
        <dd>{rupees(totals.subtotal_paise, { decimals: true })}</dd>
      </div>
      {totals.discount_paise > 0 && (
        <div className="flex justify-between text-emerald-700">
          <dt>Discount{couponCode ? ` (${couponCode})` : ""}</dt>
          <dd>−{rupees(totals.discount_paise, { decimals: true })}</dd>
        </div>
      )}
      <div className="flex justify-between">
        <dt>Shipping</dt>
        <dd>{totals.shipping_paise ? rupees(totals.shipping_paise, { decimals: true }) : "Free"}</dd>
      </div>
      <div className="flex justify-between border-t pt-2 text-base font-semibold">
        <dt>Total</dt>
        <dd>{rupees(totals.total_paise, { decimals: true })}</dd>
      </div>
      <p className="text-xs text-muted-foreground">
        {totals.prices_include_tax
          ? `Includes ${rupees(totals.tax_paise, { decimals: true })} GST`
          : `Plus ${rupees(totals.tax_paise, { decimals: true })} GST`}
      </p>
    </dl>
  )
}

function Line({ item }: { item: CartOut["items"][number] }) {
  const [pending, start] = useTransition()
  const run = (fn: () => Promise<{ ok: boolean; error?: string }>) =>
    start(async () => {
      const r = await fn()
      if (!r.ok) toast.error(r.error)
    })

  return (
    <li className="flex gap-4 py-5" aria-busy={pending}>
      <Link href={`/product/${item.product_slug}`} className="w-24 shrink-0">
        <ProductImage src={item.image_url} alt={item.product_title} seed={item.product_slug} sizes="96px" bare />
      </Link>
      <div className="flex flex-1 flex-col gap-1">
        <div className="flex justify-between gap-4">
          <div>
            <Link href={`/product/${item.product_slug}`} className="font-medium hover:underline">
              {item.product_title}
            </Link>
            <p className="text-sm text-muted-foreground">{item.variant_title}</p>
          </div>
          <p className="font-medium">{rupees(item.line_total_paise)}</p>
        </div>
        {item.issue === "UNAVAILABLE" && (
          <p className="text-sm text-destructive">No longer available. Please remove it to continue.</p>
        )}
        {item.issue === "INSUFFICIENT_STOCK" && (
          <p className="text-sm text-destructive">Only {item.max_purchasable} left. Please reduce the quantity.</p>
        )}
        <div className="mt-auto flex items-center gap-3">
          <div className="flex items-center rounded-lg border" role="group" aria-label={`Quantity of ${item.product_title}`}>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Decrease quantity"
              disabled={pending || item.quantity <= 1}
              onClick={() => run(() => updateCartItem(item.id, item.quantity - 1))}
            >
              <Minus />
            </Button>
            <span className="w-7 text-center text-sm tabular-nums">{item.quantity}</span>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Increase quantity"
              disabled={pending || item.quantity >= item.max_purchasable}
              onClick={() => run(() => updateCartItem(item.id, item.quantity + 1))}
            >
              <Plus />
            </Button>
          </div>
          <Button
            variant="ghost"
            size="sm"
            disabled={pending}
            onClick={() => run(() => removeCartItem(item.id))}
            className="text-muted-foreground"
          >
            <Trash2 /> Remove
          </Button>
        </div>
      </div>
    </li>
  )
}

function CouponForm({ cart }: { cart: CartOut }) {
  const [state, action] = useActionState(applyCoupon, null)
  const [pending, start] = useTransition()
  if (cart.coupon_code) {
    return (
      <div className="space-y-1">
        <div className="flex items-center justify-between rounded-lg bg-secondary px-3 py-2 text-sm">
          <span>
            Coupon <strong>{cart.coupon_code}</strong>
          </span>
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label="Remove coupon"
            disabled={pending}
            onClick={() => start(async () => void (await removeCoupon()))}
          >
            <X />
          </Button>
        </div>
        {cart.coupon_error && <p className="text-sm text-destructive">{cart.coupon_error}</p>}
      </div>
    )
  }
  return (
    <form action={action} className="space-y-2">
      <div className="flex gap-2">
        <Input name="code" placeholder="Coupon code" aria-label="Coupon code" required maxLength={40} className="uppercase" />
        <SubmitButton variant="outline">Apply</SubmitButton>
      </div>
      {state && !state.ok && <FormMessage state={state} />}
    </form>
  )
}

export function CartView({ cart, signedIn }: { cart: CartOut; signedIn: boolean }) {
  return (
    <div className="grid gap-10 lg:grid-cols-[1fr_360px]">
      <ul className="divide-y border-y">
        {cart.items.map((item) => (
          <Line key={item.id} item={item} />
        ))}
      </ul>
      <aside className="h-fit space-y-5 border bg-card p-6 lg:sticky lg:top-24">
        <h2 className="eyebrow text-foreground">Order summary</h2>
        <CouponForm cart={cart} />
        <TotalsTable totals={cart.totals} couponCode={cart.coupon_error ? null : cart.coupon_code} />
        <Button asChild size="lg" className="h-11 w-full text-base" disabled={!cart.checkout_ready}>
          {cart.checkout_ready ? (
            <Link href={signedIn ? "/checkout" : "/login?next=/checkout"}>{signedIn ? "Checkout" : "Sign in to checkout"}</Link>
          ) : (
            <span aria-disabled>Fix the items above to checkout</span>
          )}
        </Button>
        {cart.totals.shipping_paise > 0 && (
          <p className="text-center text-xs text-muted-foreground">Add a little more for free shipping over ₹999.</p>
        )}
      </aside>
    </div>
  )
}
