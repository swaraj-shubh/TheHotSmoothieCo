"use client"

import { usePathname, useRouter } from "next/navigation"
import { Suspense, useActionState, useEffect, useState, useTransition } from "react"

import { cancelOrder, deleteAddress, requestReturn, saveAddress, updateProfile } from "@/app/actions/account"
import { changePassword } from "@/app/actions/auth"
import { initiatePayment, paymentStatus } from "@/app/actions/checkout"
import { submitReview } from "@/app/actions/shop"
import type { AddressOut, InitiateOut, UserOut } from "@/lib/api/types"
import Link from "next/link"

import { Field, FormMessage, SubmitButton } from "./forms"
import { PayButton } from "./payment"
import { toast } from "./toast"

const LINKS = [
  ["/account", "Profile"],
  ["/account/orders", "Orders"],
  ["/account/addresses", "Addresses"],
  ["/wishlist", "Wishlist"],
]

function Links({ path }: { path: string }) {
  return LINKS.map(([href, label]) => (
    <Link key={href} href={href} aria-current={(href === "/account" ? path === href : path.startsWith(href)) ? "page" : undefined}>
      <span>{label}</span>
    </Link>
  ))
}

function RoutedLinks() {
  return <Links path={usePathname()} />
}

export function AccountLinks() {
  return (
    <Suspense fallback={<Links path="" />}>
      <RoutedLinks />
    </Suspense>
  )
}

export function ProfileForm({ user }: { user: UserOut }) {
  const [state, action] = useActionState(updateProfile, null)
  return (
    <form action={action} className="auth-form">
      <FormMessage state={state} />
      <Field label="Full name" name="full_name" defaultValue={user.full_name} required state={state} />
      <Field label="Phone" name="phone" type="tel" defaultValue={user.phone ?? ""} state={state} />
      <label style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <input type="checkbox" name="marketing_emails" defaultChecked={(user.preferences as { marketing_emails?: boolean }).marketing_emails !== false} />
        Email me about new drops and offers
      </label>
      <SubmitButton style={{ width: "fit-content" }}>[ Save changes ]</SubmitButton>
    </form>
  )
}

export function ChangePasswordForm() {
  const [state, action] = useActionState(changePassword, null)
  return (
    <form action={action} className="auth-form">
      <FormMessage state={state} />
      <Field label="Current password" name="current_password" type="password" autoComplete="current-password" required state={state} />
      <Field label="New password" name="new_password" type="password" autoComplete="new-password" required minLength={8} state={state} />
      <SubmitButton className="btn btn--outline" style={{ width: "fit-content" }}>
        [ Change password ]
      </SubmitButton>
    </form>
  )
}

function AddressForm({ address, onDone }: { address?: AddressOut; onDone: () => void }) {
  const [state, action] = useActionState(saveAddress, null)
  useEffect(() => {
    if (state?.ok) onDone()
  }, [state, onDone])
  return (
    <form action={action} className="auth-form" style={{ maxWidth: 720 }}>
      <FormMessage state={state && !state.ok ? state : null} />
      {address && <input type="hidden" name="id" value={address.id} />}
      <div className="grid-2">
        <Field label="Full name" name="full_name" autoComplete="name" required defaultValue={address?.full_name} state={state} />
        <Field label="Mobile" name="phone" type="tel" autoComplete="tel-national" required defaultValue={address?.phone} placeholder="10-digit number" state={state} />
      </div>
      <Field label="Address" name="line1" autoComplete="address-line1" required defaultValue={address?.line1} placeholder="House no, building, street" state={state} />
      <Field label="Landmark (optional)" name="landmark" defaultValue={address?.landmark ?? ""} state={state} />
      <div className="grid-2">
        <Field label="City" name="city" autoComplete="address-level2" required defaultValue={address?.city} state={state} />
        <Field label="State" name="state" autoComplete="address-level1" required defaultValue={address?.state} state={state} />
      </div>
      <div style={{ maxWidth: 240 }}>
        <Field label="Pin code" name="postal_code" inputMode="numeric" maxLength={6} autoComplete="postal-code" required defaultValue={address?.postal_code} state={state} />
      </div>
      <label style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <input type="checkbox" name="is_default_shipping" defaultChecked={address?.is_default_shipping} />
        Use as my default delivery address
      </label>
      <div style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
        <SubmitButton>[ Save address ]</SubmitButton>
        <button type="button" className="link-quiet" onClick={onDone}>
          Never mind
        </button>
      </div>
    </form>
  )
}

export function AddressBook({ addresses }: { addresses: AddressOut[] }) {
  const [editing, setEditing] = useState<string | "new" | null>(addresses.length ? null : "new")
  const [pending, start] = useTransition()
  const done = () => setEditing(null)
  return (
    <div style={{ display: "grid", gap: 24 }}>
      {addresses.map((a) =>
        editing === a.id ? (
          <AddressForm key={a.id} address={a} onDone={done} />
        ) : (
          <div key={a.id} className="order-row">
            <div style={{ display: "grid", gap: 4 }}>
              <b>
                {a.full_name} · {a.phone}
                {a.is_default_shipping && (
                  <span className="chip" style={{ marginLeft: 10 }}>
                    Default
                  </span>
                )}
              </b>
              <span className="t-cap muted">{[a.line1, a.line2, a.landmark, `${a.city}, ${a.state} ${a.postal_code}`].filter(Boolean).join(", ")}</span>
            </div>
            <div style={{ display: "flex", gap: 16 }}>
              <button className="link-quiet" onClick={() => setEditing(a.id)}>
                Edit
              </button>
              <button
                className="link-quiet"
                disabled={pending}
                onClick={() =>
                  start(async () => {
                    const r = await deleteAddress(a.id)
                    if (!r.ok) toast(r.error)
                  })
                }
              >
                Delete
              </button>
            </div>
          </div>
        ),
      )}
      {editing === "new" ? (
        <AddressForm onDone={done} />
      ) : (
        <button className="btn btn--outline" style={{ width: "fit-content" }} onClick={() => setEditing("new")}>
          [ Add address ]
        </button>
      )}
    </div>
  )
}

/** After returning from the payment widget the webhook may land a moment later: poll briefly. */
export function AwaitPayment({ orderId }: { orderId: string }) {
  const router = useRouter()
  useEffect(() => {
    let tries = 0
    const id = setInterval(async () => {
      tries += 1
      const r = await paymentStatus(orderId)
      if ((r.ok && r.data?.order_status !== "PENDING_PAYMENT") || tries >= 10) {
        clearInterval(id)
        router.refresh()
      }
    }, 2000)
    return () => clearInterval(id)
  }, [orderId, router])
  return <p className="notice">Confirming your payment…</p>
}

export function PayNow({ orderId }: { orderId: string }) {
  const [payment, setPayment] = useState<InitiateOut | null>(null)
  const [pending, start] = useTransition()
  if (payment) return <PayButton payment={payment} />
  return (
    <button
      className="btn"
      disabled={pending}
      onClick={() =>
        start(async () => {
          const r = await initiatePayment(orderId)
          if (r.ok && r.data) setPayment(r.data)
          else if (!r.ok) toast(r.error)
        })
      }
    >
      [ Complete payment ]
    </button>
  )
}

export function CancelOrder({ orderId, paid }: { orderId: string; paid: boolean }) {
  const [asking, setAsking] = useState(false)
  const [pending, start] = useTransition()
  if (!asking) {
    return (
      <button className="btn btn--outline" onClick={() => setAsking(true)}>
        [ Cancel order ]
      </button>
    )
  }
  return (
    <div className="notice" style={{ display: "grid", gap: 16, width: "100%" }}>
      <p>
        <b>Cancel this order?</b> {paid ? "You'll get a full refund to your original payment method within 5–7 working days." : "The items will be released and the order closed."}
      </p>
      <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
        <button
          className="btn"
          disabled={pending}
          onClick={() =>
            start(async () => {
              const r = await cancelOrder(orderId)
              toast(r.ok ? r.message : r.error)
              setAsking(false)
            })
          }
        >
          [ Yes, cancel ]
        </button>
        <button className="link-quiet" onClick={() => setAsking(false)}>
          Keep order
        </button>
      </div>
    </div>
  )
}

export function ReturnForm({ orderId }: { orderId: string }) {
  const [state, action] = useActionState(requestReturn, null)
  const [open, setOpen] = useState(false)
  if (state?.ok) return <FormMessage state={state} />
  if (!open) {
    return (
      <button className="btn btn--outline" onClick={() => setOpen(true)}>
        [ Request a return ]
      </button>
    )
  }
  return (
    <form action={action} className="auth-form" style={{ width: "100%" }}>
      <input type="hidden" name="order_id" value={orderId} />
      <div className="field">
        <label htmlFor="reason">What went wrong?</label>
        <textarea className="input" id="reason" name="reason" required minLength={3} maxLength={500} />
      </div>
      <FormMessage state={state} />
      <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
        <SubmitButton>[ Submit return request ]</SubmitButton>
        <button type="button" className="link-quiet" onClick={() => setOpen(false)}>
          Never mind
        </button>
      </div>
    </form>
  )
}

/** Reviews are collected from delivered orders: the design's product page has no form. */
export function ReviewForm({ productId, title }: { productId: string; title: string }) {
  const [state, action] = useActionState(submitReview, null)
  const [open, setOpen] = useState(false)
  const [rating, setRating] = useState(5)
  if (state?.ok) return <p className="t-cap muted">{state.message}</p>
  if (!open) {
    return (
      <button className="link-quiet" style={{ width: "fit-content" }} onClick={() => setOpen(true)}>
        Write a review
      </button>
    )
  }
  return (
    <form action={action} className="auth-form">
      <input type="hidden" name="product_id" value={productId} />
      <input type="hidden" name="rating" value={rating} />
      <div className="stars" role="group" aria-label={`Your rating for ${title}`}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" aria-label={`${n} star${n > 1 ? "s" : ""}`} aria-pressed={rating === n} style={{ background: "none", border: 0, padding: 0, color: "inherit", font: "inherit" }} onClick={() => setRating(n)}>
            {n <= rating ? "★" : "☆"}
          </button>
        ))}
      </div>
      <Field label="Title (optional)" name="title" maxLength={120} state={state} />
      <div className="field">
        <label htmlFor={`body-${productId}`}>Your review (optional)</label>
        <textarea className="input" id={`body-${productId}`} name="body" maxLength={5000} />
      </div>
      <FormMessage state={state} />
      <SubmitButton style={{ width: "fit-content" }}>[ Submit review ]</SubmitButton>
    </form>
  )
}
