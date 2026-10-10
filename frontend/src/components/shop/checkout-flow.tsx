"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useState, useTransition } from "react"
import { toast } from "sonner"

import { placeOrder, type PlacedOrder } from "@/app/actions/checkout"
import { Button } from "@/components/ui/button"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Textarea } from "@/components/ui/textarea"
import type { AddressOut, CartOut } from "@/lib/api/types"
import { rupees } from "@/lib/format"

import { AddressForm } from "./address-form"
import { TotalsTable } from "./cart-view"
import { PayButton } from "./payment"

function AddressLine({ a }: { a: AddressOut }) {
  return (
    <span className="text-sm">
      <span className="font-medium">{a.full_name}</span> · {a.phone}
      <br />
      <span className="text-muted-foreground">
        {[a.line1, a.line2, a.landmark, `${a.city}, ${a.state} ${a.postal_code}`].filter(Boolean).join(", ")}
      </span>
    </span>
  )
}

export function CheckoutFlow({ cart, addresses }: { cart: CartOut; addresses: AddressOut[] }) {
  const router = useRouter()
  const initial = addresses.find((a) => a.is_default_shipping) ?? addresses[0]
  const [addressId, setAddressId] = useState(initial?.id ?? "")
  const [adding, setAdding] = useState(addresses.length === 0)
  const [notes, setNotes] = useState("")
  const [placed, setPlaced] = useState<PlacedOrder | null>(null)
  const [pending, start] = useTransition()
  // One key per checkout visit: retries and double clicks can never create a second order.
  const [idempotencyKey] = useState(() => crypto.randomUUID())

  function submit() {
    start(async () => {
      const r = await placeOrder({ addressId, expectedTotalPaise: cart.totals.total_paise, idempotencyKey, notes })
      if (r.ok && r.data) return setPlaced(r.data)
      if (!r.ok && r.code === "PRICE_CHANGED") {
        toast.error("Prices changed since you opened checkout. Please review your cart.")
        return router.push("/cart")
      }
      if (!r.ok) toast.error(r.error)
    })
  }

  if (placed) {
    return (
      <div className="mx-auto max-w-lg space-y-6 border bg-card p-8 text-center">
        <p className="font-display text-3xl">Almost there!</p>
        <p>
          Order <strong>{placed.order.number}</strong> is reserved for you. Complete payment within 15 minutes to confirm it.
        </p>
        <PayButton payment={placed.payment} />
        <Link href={`/account/orders/${placed.order.id}`} className="block text-sm text-muted-foreground underline">
          View order
        </Link>
      </div>
    )
  }

  return (
    <div className="grid gap-10 lg:grid-cols-[1fr_380px]">
      <div className="space-y-8">
        <section aria-labelledby="ship-to" className="space-y-4">
          <h2 id="ship-to" className="eyebrow text-foreground">
            1. Delivery address
          </h2>
          {addresses.length > 0 && !adding && (
            <RadioGroup value={addressId} onValueChange={setAddressId} className="space-y-2">
              {addresses.map((a) => (
                <label
                  key={a.id}
                  className="flex cursor-pointer gap-3 border p-4 has-[[data-state=checked]]:border-foreground"
                >
                  <RadioGroupItem value={a.id} className="mt-1" />
                  <AddressLine a={a} />
                </label>
              ))}
            </RadioGroup>
          )}
          {adding ? (
            <div className=" border p-5">
              <AddressForm
                submitLabel="Save and use this address"
                onSaved={(a) => {
                  setAddressId(a.id)
                  setAdding(false)
                  router.refresh()
                }}
              />
              {addresses.length > 0 && (
                <Button variant="link" className="mt-2 px-0" onClick={() => setAdding(false)}>
                  Cancel
                </Button>
              )}
            </div>
          ) : (
            <Button variant="outline" onClick={() => setAdding(true)}>
              + Add a new address
            </Button>
          )}
        </section>

        <section aria-labelledby="review" className="space-y-4">
          <h2 id="review" className="eyebrow text-foreground">
            2. Review your order
          </h2>
          <ul className="divide-y border">
            {cart.items.map((i) => (
              <li key={i.id} className="flex justify-between gap-4 p-4 text-sm">
                <span>
                  {i.product_title} <span className="text-muted-foreground">· {i.variant_title} × {i.quantity}</span>
                </span>
                <span className="font-medium">{rupees(i.line_total_paise)}</span>
              </li>
            ))}
          </ul>
          <label className="block space-y-1.5 text-sm">
            <span className="font-medium">Delivery notes (optional)</span>
            <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={500} rows={2} />
          </label>
        </section>
      </div>

      <aside className="h-fit space-y-5 border bg-card p-6 lg:sticky lg:top-24">
        <h2 className="eyebrow text-foreground">3. Pay</h2>
        <TotalsTable totals={cart.totals} couponCode={cart.coupon_code} />
        <Button
          size="lg"
          className="h-11 w-full text-base"
          disabled={!addressId || adding || pending || !cart.checkout_ready}
          onClick={submit}
        >
          {pending ? "Placing order…" : "Place order & pay"}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          Payments are processed securely by Razorpay. Cards, UPI, net banking and wallets accepted.
        </p>
      </aside>
    </div>
  )
}
