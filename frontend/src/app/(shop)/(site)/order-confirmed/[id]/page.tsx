import type { Metadata } from "next"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"
import { Suspense } from "react"

import { Address, OrderLines } from "@/components/sf/order-bits"
import { api, unwrapOrNull } from "@/lib/api/client"
import { money } from "@/lib/format"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Order confirmed", robots: { index: false } }

async function Confirmed({ params }: { params: PageProps<"/order-confirmed/[id]">["params"] }) {
  const [{ id }, user] = await Promise.all([params, requireUser("/account/orders")])
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound()
  const order = unwrapOrNull(await (await api()).GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } }))
  if (!order) notFound()
  // Not paid (yet): the order page polls for the webhook, then comes back here.
  if (order.status !== "CONFIRMED") redirect(`/account/orders/${id}?placed=1`)
  const first = String((order.shipping_address as Record<string, string | null>).full_name ?? "").split(" ")[0]
  return (
    <>
      <div style={{ display: "grid", gap: 20, maxWidth: 900, marginBottom: 56 }}>
        <span className="chip" style={{ width: "fit-content" }}>
          ORDER <span style={{ marginLeft: 6 }}>{order.number}</span>
        </span>
        <h1 className="t-display">Done, {first}. Your walls are about to get interesting.</h1>
        <p className="t-sub">
          We have sent the details to <b>{user.email}</b>. Most orders reach you in 4-5 days.
        </p>
      </div>
      <div className="cart-layout">
        <div>
          <h2 className="t-head" style={{ marginBottom: 24 }}>
            What happens next
          </h2>
          <div className="order-steps">
            <div className="step">
              <span className="t-price muted">01</span>
              <h3 className="t-head">Picked</h3>
              <p className="muted">Your posters are pulled from the drop.</p>
            </div>
            <div className="step">
              <span className="t-price muted">02</span>
              <h3 className="t-head">Printed</h3>
              <p className="muted">300 GSM glossy, colours turned up.</p>
            </div>
            <div className="step">
              <span className="t-price muted">03</span>
              <h3 className="t-head">Packed</h3>
              <p className="muted">Tamper-proof, then on its way to you.</p>
            </div>
          </div>
          <h2 className="t-head" style={{ margin: "56px 0 12px" }}>
            Delivering to
          </h2>
          <Address order={order} />
          <div style={{ display: "flex", gap: 20, marginTop: 40, flexWrap: "wrap", alignItems: "center" }}>
            <Link className="btn" href="/shop">
              [ Keep browsing ]
            </Link>
            <Link className="btn-link" href="/contact">
              Need help? Tell us <span aria-hidden="true">→</span>
            </Link>
          </div>
        </div>
        <aside className="summary" aria-label="Order summary">
          <h2 className="t-head">Order summary</h2>
          <div style={{ display: "grid", gap: 20 }}>
            <OrderLines order={order} />
            <div className="summary__row summary__row--total t-price">
              <span>Total</span>
              <span>{money(order.total_paise)}</span>
            </div>
          </div>
        </aside>
      </div>
    </>
  )
}

/** The design's order-confirmed page, reached straight after a successful payment. */
export default function OrderConfirmedPage(props: PageProps<"/order-confirmed/[id]">) {
  return (
    <section className="wrap" style={{ paddingTop: 64, paddingBottom: 96 }}>
      <Suspense fallback={null}>
        <Confirmed params={props.params} />
      </Suspense>
    </section>
  )
}
