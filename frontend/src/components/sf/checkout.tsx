"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"

import { saveAddress } from "@/app/actions/account"
import { placeOrder, type PlacedOrder } from "@/app/actions/checkout"
import type { AddressOut, CartOut } from "@/lib/api/types"
import { cdn, money, sizeOf } from "@/lib/format"

import { SummaryRows } from "./cart"
import { Field } from "./forms"
import { PayButton } from "./payment"
import { toast } from "./toast"

const RULES: Record<string, (v: string) => true | string> = {
  full_name: (v) => v.trim().length > 1 || "We need a name for the parcel.",
  phone: (v) => /^(\+?91)?[6-9]\d{9}$/.test(v.replace(/\s/g, "")) || "Enter a 10-digit mobile number.",
  line1: (v) => v.trim().length > 4 || "Where should the croc deliver?",
  city: (v) => v.trim().length > 1 || "City, please.",
  state: (v) => v.trim().length > 1 || "State, please.",
  postal_code: (v) => /^[1-9]\d{5}$/.test(v) || "Pin code is 6 digits.",
}

const line = (a: AddressOut) => [a.line1, a.line2, a.landmark, `${a.city}, ${a.state} ${a.postal_code}`].filter(Boolean).join(", ")

export function MiniLine({ image, title, detail, price }: { image?: string | null; title: string; detail: string; price: number }) {
  return (
    <div className="mini">
      <img src={image ? cdn(image, 200) : "/assets/croc-wordmark.png"} alt="" />
      <div>
        <p>{title}</p>
        <p className="t-cap muted">{detail}</p>
      </div>
      <span className="t-cap">{money(price)}</span>
    </div>
  )
}

const fieldset = { border: 0, padding: 0, margin: "0 0 36px" }
const legend = { marginBottom: 20, padding: 0 }

export function CheckoutFlow({ cart, addresses, email }: { cart: CartOut; addresses: AddressOut[]; email: string }) {
  const router = useRouter()
  const initial = addresses.find((a) => a.is_default_shipping) ?? addresses[0]
  const [addressId, setAddressId] = useState(initial?.id ?? "")
  const [adding, setAdding] = useState(addresses.length === 0)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [placed, setPlaced] = useState<PlacedOrder | null>(null)
  const [pay, setPay] = useState<"upi" | "online">("upi")
  const [pending, start] = useTransition()
  // One key per checkout visit: retries and double clicks can never create a second order.
  const [idempotencyKey] = useState(() => crypto.randomUUID())

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    if (adding) {
      const found: Record<string, string> = {}
      for (const [name, rule] of Object.entries(RULES)) {
        const r = rule(String(form.get(name) ?? ""))
        if (r !== true) found[name] = r
      }
      setErrors(found)
      const first = Object.keys(found)[0]
      if (first) return void (e.currentTarget.elements.namedItem(first) as HTMLElement)?.focus()
    }
    start(async () => {
      let shipTo = addressId
      if (adding) {
        form.set("is_default_shipping", "on")
        const saved = await saveAddress(null, form)
        if (!saved.ok || !saved.data) {
          if (!saved.ok && saved.fields) setErrors(saved.fields)
          return toast(saved.ok ? "Could not save that address." : saved.error)
        }
        shipTo = saved.data.id
        setAddressId(shipTo)
        setAdding(false)
      }
      const r = await placeOrder({ addressId: shipTo, expectedTotalPaise: cart.totals.total_paise, idempotencyKey })
      if (r.ok && r.data) return setPlaced(r.data)
      if (!r.ok && r.code === "PRICE_CHANGED") {
        toast("Prices changed since you opened checkout. Please review your cart.")
        return router.push("/cart")
      }
      if (!r.ok) toast(r.error)
    })
  }

  return (
    <div className="cart-layout">
      {placed ? (
        <div>
          <div className="check-sec">
            <h2 className="t-head">Pay however you like</h2>
            <p>
              Order <b>{placed.order.number}</b> is reserved for you. Complete payment within 15 minutes to confirm it.
            </p>
            <PayButton payment={placed.payment} method={pay === "upi" ? "upi" : undefined} />
            <Link className="link-quiet" href={`/account/orders/${placed.order.id}`} style={{ width: "fit-content" }}>
              View order
            </Link>
          </div>
        </div>
      ) : (
        <form onSubmit={submit} noValidate>
          <fieldset className="check-sec" style={fieldset}>
            <legend className="t-head" style={legend}>
              Contact
            </legend>
            <Field label="Email" name="email" type="email" value={email} readOnly />
          </fieldset>
          <fieldset className="check-sec" style={fieldset}>
            <legend className="t-head" style={legend}>
              Where does it go?
            </legend>
            {addresses.length > 0 && !adding && (
              <>
                {addresses.map((a) => (
                  <label key={a.id} className="radio-card">
                    <input type="radio" name="address" value={a.id} checked={addressId === a.id} onChange={() => setAddressId(a.id)} />
                    <div>
                      <b>
                        {a.full_name} · {a.phone}
                      </b>
                      <span className="t-cap muted">{line(a)}</span>
                    </div>
                  </label>
                ))}
                <button type="button" className="btn-link" style={{ width: "fit-content" }} onClick={() => setAdding(true)}>
                  Use a new address <span aria-hidden="true">→</span>
                </button>
              </>
            )}
            {adding && (
              <>
                <div className="grid-2">
                  <Field label="Full name" name="full_name" autoComplete="name" error={errors.full_name} />
                  <Field label="Mobile" name="phone" type="tel" inputMode="numeric" autoComplete="tel-national" placeholder="10-digit number" error={errors.phone} />
                </div>
                <Field label="Address" name="line1" autoComplete="address-line1" placeholder="House no, building, street" error={errors.line1} />
                <Field label="Landmark (optional)" name="landmark" autoComplete="address-line2" error={errors.landmark} noError={!errors.landmark} />
                <div className="grid-2">
                  <Field label="City" name="city" autoComplete="address-level2" error={errors.city} />
                  <Field label="State" name="state" autoComplete="address-level1" error={errors.state} />
                </div>
                <div style={{ maxWidth: 240 }}>
                  <Field label="Pin code" name="postal_code" inputMode="numeric" maxLength={6} autoComplete="postal-code" error={errors.postal_code} />
                </div>
                {addresses.length > 0 && (
                  <button type="button" className="link-quiet" style={{ width: "fit-content" }} onClick={() => setAdding(false)}>
                    Use a saved address
                  </button>
                )}
              </>
            )}
          </fieldset>
          <fieldset className="check-sec" style={fieldset}>
            <legend className="t-head" style={legend}>
              Pay however you like
            </legend>
            <label className="radio-card">
              <input type="radio" name="pay" value="upi" checked={pay === "upi"} onChange={() => setPay("upi")} />
              <div>
                <b>UPI</b>
                <span className="t-cap muted">GPay, PhonePe, Paytm. Fastest way to your wall.</span>
              </div>
            </label>
            <label className="radio-card">
              <input type="radio" name="pay" value="online" checked={pay === "online"} onChange={() => setPay("online")} />
              <div>
                <b>Card / Netbanking</b>
                <span className="t-cap muted">You will finish on our secure payment page.</span>
              </div>
            </label>
          </fieldset>
          <button className="btn btn--block" type="submit" style={{ padding: 18 }} disabled={pending || !cart.checkout_ready}>
            {pending ? "[ Placing order ]" : "[ Place order ]"}
          </button>
          <p className="t-cap muted" style={{ marginTop: 14, textAlign: "center" }}>
            By placing your order you agree to our{" "}
            <Link href="/shipping-returns" style={{ textDecoration: "underline" }}>
              shipping &amp; returns policy
            </Link>
            .
          </p>
        </form>
      )}
      <aside className="summary" aria-label="Order summary">
        <h2 className="t-head">Your order</h2>
        <div style={{ display: "grid", gap: 20 }}>
          {cart.items.map((i) => (
            <MiniLine key={i.id} image={i.image_url} title={i.product_title} detail={`${sizeOf(i)} × ${i.quantity}`} price={i.line_total_paise} />
          ))}
          <SummaryRows totals={cart.totals} code={cart.coupon_code} />
        </div>
        <Link className="link-quiet" href="/cart" style={{ width: "fit-content" }}>
          Edit cart
        </Link>
      </aside>
    </div>
  )
}
