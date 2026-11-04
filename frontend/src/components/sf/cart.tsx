"use client"

import Link from "next/link"
import { useState, useTransition } from "react"

import { applyCoupon, removeCartItem, removeCoupon, updateCartItem } from "@/app/actions/cart"
import type { CartOut } from "@/lib/api/types"
import { cdn, money, sizeOf } from "@/lib/format"
import { SITE } from "@/lib/site"

import { toast } from "./toast"

/** Subtotal -> total rows shared by the cart, checkout and order pages. */
export function SummaryRows({ totals, code }: { totals: CartOut["totals"]; code?: string | null }) {
  const pct = totals.subtotal_paise ? Math.round((totals.discount_paise / totals.subtotal_paise) * 100) : 0
  return (
    <>
      <div className="summary__row">
        <span>Subtotal</span>
        <span>{money(totals.subtotal_paise)}</span>
      </div>
      {totals.discount_paise > 0 && (
        <div className="summary__row brand">
          <span>
            {code} (−{pct}%)
          </span>
          <span>− {money(totals.discount_paise)}</span>
        </div>
      )}
      <div className="summary__row">
        <span>Delivery</span>
        <span>{totals.shipping_paise ? money(totals.shipping_paise) : "Free"}</span>
      </div>
      {!totals.prices_include_tax && (
        <div className="summary__row">
          <span>GST</span>
          <span>{money(totals.tax_paise)}</span>
        </div>
      )}
      <div className="summary__row summary__row--total t-price">
        <span>Total</span>
        <span>{money(totals.total_paise)}</span>
      </div>
    </>
  )
}

function Line({ item }: { item: CartOut["items"][number] }) {
  const [pending, start] = useTransition()
  const [leaving, setLeaving] = useState(false)
  const run = (fn: () => Promise<{ ok: boolean; error?: string }>) =>
    start(async () => {
      const r = await fn()
      if (!r.ok) {
        setLeaving(false)
        toast(r.error)
      }
    })
  const remove = () => {
    setLeaving(true)
    setTimeout(() => run(() => removeCartItem(item.id)), 330)
  }
  const href = `/product/${item.product_slug}`
  return (
    <div className={`line${leaving ? " leaving" : ""}`} aria-busy={pending}>
      <Link href={href}>{item.image_url ? <img src={cdn(item.image_url, 400)} alt="" /> : <img src="/assets/croc-wordmark.png" alt="" />}</Link>
      <div className="line__info">
        <Link className="t-sub" href={href}>
          {item.product_title}
        </Link>
        <span className="t-cap muted">Size {sizeOf(item)}</span>
        {item.issue === "UNAVAILABLE" && <span className="t-cap brand">No longer available. Please remove it to continue.</span>}
        {item.issue === "INSUFFICIENT_STOCK" && <span className="t-cap brand">Only {item.max_purchasable} left. Please reduce the quantity.</span>}
        <button className="link-quiet" style={{ width: "fit-content" }} onClick={remove}>
          Remove
        </button>
      </div>
      <div className="line__end">
        <span className="t-price">{money(item.line_total_paise)}</span>
        <div className="stepper" role="group" aria-label={`Quantity for ${item.product_title}`}>
          <button aria-label="Fewer" disabled={pending} onClick={() => (item.quantity <= 1 ? remove() : run(() => updateCartItem(item.id, item.quantity - 1)))}>
            −
          </button>
          <output>{item.quantity}</output>
          <button aria-label="More" disabled={pending || item.quantity >= Math.min(10, item.max_purchasable)} onClick={() => run(() => updateCartItem(item.id, item.quantity + 1))}>
            +
          </button>
        </div>
      </div>
    </div>
  )
}

function Coupon({ cart }: { cart: CartOut }) {
  const [error, setError] = useState<string | undefined>()
  const [pending, start] = useTransition()
  return (
    <form
      className="field"
      onSubmit={(e) => {
        e.preventDefault()
        const form = new FormData(e.currentTarget)
        const code = String(form.get("code") ?? "").trim().toUpperCase()
        start(async () => {
          form.set("code", code)
          const r = code ? await applyCoupon(null, form) : await removeCoupon()
          setError(r.ok ? undefined : r.error)
        })
      }}
    >
      <label htmlFor="code">Promo code</label>
      <div style={{ display: "flex", gap: 8 }}>
        <input className="input input--pill" id="code" name="code" placeholder="WELCOME10" defaultValue={cart.coupon_code ?? ""} autoComplete="off" maxLength={40} />
        <button className="btn btn--outline" type="submit" disabled={pending}>
          Apply
        </button>
      </div>
      <span className="err" role="alert">
        {error ?? cart.coupon_error}
      </span>
    </form>
  )
}

export function CartView({ cart, signedIn }: { cart: CartOut; signedIn: boolean }) {
  const t = cart.totals
  const goods = t.subtotal_paise - t.discount_paise
  const away = Math.max(0, SITE.freeShippingAbovePaise - goods)
  const pct = Math.min(100, Math.round((goods / SITE.freeShippingAbovePaise) * 100))
  return (
    <div className="cart-layout first-draw">
      <section aria-label="Items in your cart">
        {cart.items.map((item) => (
          <Line key={item.id} item={item} />
        ))}
        <Link className="btn-link" href="/shop" style={{ marginTop: 24 }}>
          Keep browsing →
        </Link>
      </section>
      <aside className="summary" aria-label="Order summary">
        <h2 className="t-head">Summary</h2>
        <div>
          <p className="t-cap" style={{ marginBottom: 8 }}>
            {away > 0 ? (
              <>
                You&apos;re <b>{money(away)}</b> away from free delivery.
              </>
            ) : (
              "Free delivery unlocked. The croc approves."
            )}
          </p>
          <div className="meter">
            <i style={{ width: `${pct}%` }} />
          </div>
        </div>
        <SummaryRows totals={t} code={cart.coupon_code} />
        <Coupon cart={cart} />
        {cart.checkout_ready ? (
          <Link className="btn btn--block" href={signedIn ? "/checkout" : "/login?next=/checkout"}>
            [ Checkout ]
          </Link>
        ) : (
          <button className="btn btn--block" disabled>
            [ Fix the items above ]
          </button>
        )}
        <p className="t-cap muted" style={{ textAlign: "center" }}>
          UPI, cards &amp; netbanking accepted
        </p>
      </aside>
    </div>
  )
}
