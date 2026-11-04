import type { Metadata } from "next"
import Link from "next/link"
import { notFound, redirect } from "next/navigation"
import { Suspense } from "react"

import { AwaitPayment, CancelOrder, PayNow, ReturnForm, ReviewForm } from "@/components/sf/account"
import { SummaryRows } from "@/components/sf/cart"
import { Address, OrderLines } from "@/components/sf/order-bits"
import { api, unwrapOrNull } from "@/lib/api/client"
import type { OrderOut } from "@/lib/api/types"
import { formatDate, formatDateTime, orderLabel, titleCase } from "@/lib/format"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Order details", robots: { index: false } }

const CANCELLABLE = new Set(["PENDING_PAYMENT", "CONFIRMED", "PROCESSING"])
const RETURN_WINDOW_DAYS = 7

function Totals({ order }: { order: OrderOut }) {
  return <SummaryRows totals={order} code={order.coupon_code} />
}

async function Order({ params, searchParams }: PageProps<"/account/orders/[id]">) {
  const [{ id }, sp] = await Promise.all([params, searchParams, requireUser()])
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound()
  const client = await api()
  const order = unwrapOrNull(await client.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } }))
  if (!order) notFound()
  if (sp.placed && order.status === "CONFIRMED") redirect(`/order-confirmed/${id}`)
  // Tracking is nice-to-have: if it fails, show the order without it.
  const { data: shipments = [] } = await client.GET("/api/v1/shipping/orders/{order_id}", { params: { path: { order_id: id } } })

  const delivered = [...order.history].reverse().find((h) => h.to_status === "DELIVERED")
  const canReturn =
    order.status === "DELIVERED" &&
    !!delivered &&
    // eslint-disable-next-line react-hooks/purity -- server component, rendered per request
    (Date.now() - Date.parse(delivered.created_at)) / 86_400_000 <= RETURN_WINDOW_DAYS

  return (
    <div style={{ display: "grid", gap: 40 }}>
      <div style={{ display: "grid", gap: 16 }}>
        <span className="chip chip--outline" style={{ width: "fit-content" }}>
          {orderLabel(order.status)}
        </span>
        <h1 className="t-display">Order {order.number}.</h1>
        <p className="t-cap muted">Placed {formatDate(order.created_at)}</p>
      </div>

      {order.status === "PENDING_PAYMENT" &&
        (sp.placed ? (
          <AwaitPayment orderId={order.id} />
        ) : (
          <div className="notice" style={{ display: "grid", gap: 16 }}>
            <p>
              Payment pending.
              {order.payment_due_at && ` Pay by ${formatDateTime(order.payment_due_at)} to keep your items reserved.`}
            </p>
            <div>
              <PayNow orderId={order.id} />
            </div>
          </div>
        ))}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
        {CANCELLABLE.has(order.status) && !shipments.some((s) => s.status !== "CANCELLED") && <CancelOrder orderId={order.id} paid={order.status !== "PENDING_PAYMENT"} />}
        {canReturn && <ReturnForm orderId={order.id} />}
      </div>

      <div className="cart-layout">
        <div style={{ display: "grid", gap: 56 }}>
          {order.status === "DELIVERED" && (
            <div style={{ display: "grid", gap: 24 }}>
              <h2 className="t-head">Tell us what you think</h2>
              {order.items.map((i) => (
                <div key={i.id} style={{ display: "grid", gap: 8 }}>
                  <b>{i.product_title}</b>
                  <ReviewForm productId={i.product_id} title={i.product_title} />
                </div>
              ))}
            </div>
          )}
          <div>
            <h2 className="t-head" style={{ marginBottom: 12 }}>
              Delivering to
            </h2>
            <Address order={order} />
          </div>
          {shipments.length > 0 && (
            <div style={{ display: "grid", gap: 24 }}>
              <h2 className="t-head">Tracking</h2>
              {shipments.map((s) => (
                <div key={s.id} style={{ display: "grid", gap: 12 }}>
                  <p>
                    <b>{s.is_return ? "Return pickup" : (s.courier ?? "Courier")}</b>
                    {s.awb && <span className="t-cap muted"> · AWB {s.awb}</span>} · {titleCase(s.status)}
                  </p>
                  {s.events.length > 0 && (
                    <ol className="timeline">
                      {[...s.events].reverse().map((e, i) => (
                        <li key={i}>
                          <b>{e.raw_status}</b>
                          {e.location && <span className="t-cap muted"> · {e.location}</span>}
                          <span className="t-cap muted" style={{ display: "block" }}>
                            {formatDateTime(e.occurred_at)}
                          </span>
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              ))}
            </div>
          )}
          <div style={{ display: "grid", gap: 24 }}>
            <h2 className="t-head">History</h2>
            <ol className="timeline">
              {order.history.map((h, i) => (
                <li key={i}>
                  <b>{orderLabel(h.to_status)}</b>
                  <span className="t-cap muted"> · {formatDateTime(h.created_at)}</span>
                </li>
              ))}
            </ol>
          </div>
          <Link className="btn-link" href="/account/orders" style={{ width: "fit-content" }}>
            All orders
          </Link>
        </div>
        <aside className="summary" aria-label="Order summary">
          <h2 className="t-head">Order summary</h2>
          <div style={{ display: "grid", gap: 20 }}>
            <OrderLines order={order} />
            <Totals order={order} />
          </div>
        </aside>
      </div>
    </div>
  )
}

export default function OrderPage(props: PageProps<"/account/orders/[id]">) {
  return (
    <Suspense fallback={null}>
      <Order {...props} />
    </Suspense>
  )
}
