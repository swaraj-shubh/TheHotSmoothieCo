import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import { Suspense } from "react"
import { CheckCircle2, Package, Truck } from "lucide-react"

import { AwaitPayment, CancelOrder, PayNow, ReturnForm } from "@/components/account/order-actions"
import { OrderStatusBadge } from "@/components/account/order-status"
import { ProductImage } from "@/components/shop/product-image"
import { api, unwrapOrNull } from "@/lib/api/client"
import { formatDate, formatDateTime, rupees, titleCase } from "@/lib/format"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Order details", robots: { index: false } }

const CANCELLABLE = new Set(["PENDING_PAYMENT", "CONFIRMED", "PROCESSING"])
const RETURN_WINDOW_DAYS = 7

async function Order({ params, searchParams }: PageProps<"/account/orders/[id]">) {
  const [{ id }, sp] = await Promise.all([params, searchParams, requireUser()])
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound()
  const client = await api()
  const order = unwrapOrNull(await client.GET("/api/v1/orders/{order_id}", { params: { path: { order_id: id } } }))
  if (!order) notFound()
  // Tracking is nice-to-have: if it fails, show the order without it.
  const { data: shipments = [] } = await client.GET("/api/v1/shipping/orders/{order_id}", {
    params: { path: { order_id: id } },
  })

  const delivered = [...order.history].reverse().find((h) => h.to_status === "DELIVERED")
  const canReturn =
    order.status === "DELIVERED" &&
    !!delivered &&
    // eslint-disable-next-line react-hooks/purity -- server component, rendered per request
    (Date.now() - Date.parse(delivered.created_at)) / 86_400_000 <= RETURN_WINDOW_DAYS
  const a = order.shipping_address as Record<string, string | null>

  return (
    <div className="space-y-8">
      {sp.placed && order.status === "CONFIRMED" && (
        <div className="flex items-center gap-3 border p-6">
          <CheckCircle2 className="size-6" aria-hidden />
          <div>
            <p className="font-semibold">Thank you! Your order is confirmed.</p>
            <p className="text-sm">We’ve emailed your receipt. We’ll let you know when it ships.</p>
          </div>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="font-display text-5xl leading-none tracking-tight">Order {order.number}</h1>
        <OrderStatusBadge status={order.status} />
        <span className="text-sm text-muted-foreground">Placed {formatDate(order.created_at)}</span>
      </div>

      {order.status === "PENDING_PAYMENT" &&
        (sp.placed ? (
          <AwaitPayment orderId={order.id} />
        ) : (
          <div className="flex flex-wrap items-center gap-4 border border-amber-300 p-4 text-sm">
            <span>
              Payment pending.
              {order.payment_due_at && ` Pay by ${formatDateTime(order.payment_due_at)} to keep your items reserved.`}
            </span>
            <PayNow orderId={order.id} />
          </div>
        ))}

      <div className="flex flex-wrap gap-3">
        {CANCELLABLE.has(order.status) && !shipments.some((s) => s.status !== "CANCELLED") && (
          <CancelOrder orderId={order.id} paid={order.status !== "PENDING_PAYMENT"} />
        )}
        {canReturn && <ReturnForm orderId={order.id} />}
      </div>

      <section className="grid items-start gap-8 lg:grid-cols-[1fr_300px]">
        <ul className="divide-y border">
          {order.items.map((item) => (
            <li key={item.id} className="flex gap-4 p-4">
              <div className="w-16 shrink-0">
                <ProductImage src={item.image_url} alt={item.product_title} seed={item.sku} sizes="64px" bare />
              </div>
              <div className="flex-1 text-sm">
                <p className="font-medium">{item.product_title}</p>
                <p className="text-muted-foreground">
                  {item.variant_title} × {item.quantity}
                </p>
              </div>
              <p className="text-sm font-medium">{rupees(item.line_total_paise)}</p>
            </li>
          ))}
        </ul>
        <div className="space-y-6 text-sm">
          <dl className="space-y-2 border p-5">
            <div className="flex justify-between">
              <dt>Subtotal</dt>
              <dd>{rupees(order.subtotal_paise, { decimals: true })}</dd>
            </div>
            {order.discount_paise > 0 && (
              <div className="flex justify-between text-emerald-700">
                <dt>Discount {order.coupon_code && `(${order.coupon_code})`}</dt>
                <dd>−{rupees(order.discount_paise, { decimals: true })}</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt>Shipping</dt>
              <dd>{order.shipping_paise ? rupees(order.shipping_paise, { decimals: true }) : "Free"}</dd>
            </div>
            <div className="flex justify-between border-t pt-2 font-semibold">
              <dt>Total</dt>
              <dd>{rupees(order.total_paise, { decimals: true })}</dd>
            </div>
          </dl>
          <div className=" border p-5">
            <p className="mb-1 font-semibold">Delivering to</p>
            <p>{a.full_name}</p>
            <p className="text-muted-foreground">
              {[a.line1, a.line2, a.landmark, `${a.city}, ${a.state} ${a.postal_code}`].filter(Boolean).join(", ")}
            </p>
          </div>
        </div>
      </section>

      {shipments.length > 0 && (
        <section aria-labelledby="tracking" className="space-y-3">
          <h2 id="tracking" className="eyebrow text-foreground">
            Tracking
          </h2>
          {shipments.map((s) => (
            <div key={s.id} className=" border p-5 text-sm">
              <p className="flex items-center gap-2 font-medium">
                <Truck className="size-4" aria-hidden /> {s.is_return ? "Return pickup" : s.courier ?? "Courier"}
                {s.awb && <span className="text-muted-foreground">· AWB {s.awb}</span>}
                <span className="ml-auto">{titleCase(s.status)}</span>
              </p>
              {s.events.length > 0 && (
                <ol className="mt-3 space-y-2 border-l pl-4">
                  {[...s.events].reverse().map((e, i) => (
                    <li key={i}>
                      <span className="font-medium">{e.raw_status}</span>
                      {e.location && <span className="text-muted-foreground"> · {e.location}</span>}
                      <span className="block text-xs text-muted-foreground">{formatDateTime(e.occurred_at)}</span>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          ))}
        </section>
      )}

      <section aria-labelledby="history" className="space-y-3">
        <h2 id="history" className="eyebrow text-foreground">
          History
        </h2>
        <ol className="space-y-2 border-l pl-4 text-sm">
          {order.history.map((h, i) => (
            <li key={i} className="flex gap-2">
              <Package className="mt-0.5 size-3.5 text-muted-foreground" aria-hidden />
              <span>
                <span className="font-medium">{titleCase(h.to_status)}</span>
                <span className="text-muted-foreground"> · {formatDateTime(h.created_at)}</span>
              </span>
            </li>
          ))}
        </ol>
      </section>
      <Link href="/account/orders" className="text-sm underline underline-offset-4">
        ← All orders
      </Link>
    </div>
  )
}

export default function OrderPage(props: PageProps<"/account/orders/[id]">) {
  return (
    <Suspense fallback={<div className="h-96 animate-pulse bg-muted" />}>
      <Order {...props} />
    </Suspense>
  )
}
