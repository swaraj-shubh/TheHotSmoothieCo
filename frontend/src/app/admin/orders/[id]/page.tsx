import Link from "next/link"
import { notFound } from "next/navigation"
import { Suspense } from "react"

import { OrderStatusBadge } from "@/components/account/order-status"
import { OrderActions } from "@/components/admin/order-actions"
import { AdminPage, TableSkeleton } from "@/components/admin/ui"
import { Badge } from "@/components/ui/badge"
import { can } from "@/lib/admin-access"
import { api, unwrapOrNull } from "@/lib/api/client"
import { formatDateTime, rupees, titleCase } from "@/lib/format"
import { requireStaff } from "@/lib/session"

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-xl border bg-card p-5 text-sm">
      <h2 className="font-semibold">{title}</h2>
      {children}
    </section>
  )
}

async function Order({ params }: PageProps<"/admin/orders/[id]">) {
  const user = await requireStaff("orders")
  const { id } = await params
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound()
  const order = unwrapOrNull(await (await api()).GET("/api/v1/admin/orders/{order_id}", { params: { path: { order_id: id } } }))
  if (!order) notFound()
  const a = order.shipping_address as Record<string, string | null>

  return (
    <AdminPage
      title={`Order ${order.number}`}
      description={`Placed ${formatDateTime(order.created_at)}`}
      actions={<OrderStatusBadge status={order.status} className="text-sm" />}
    >
      <OrderActions order={order} canWrite={can(user.roles, "ordersWrite")} />
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="space-y-6">
          <Card title="Items">
            <ul className="divide-y">
              {order.items.map((i) => (
                <li key={i.id} className="flex justify-between gap-4 py-2">
                  <span>
                    {i.product_title} <span className="text-muted-foreground">· {i.variant_title} · {i.sku}</span>
                    <span className="block text-xs text-muted-foreground">
                      {i.quantity} × {rupees(i.unit_price_paise)}
                      {i.discount_paise > 0 && ` − ${rupees(i.discount_paise)} discount`}
                    </span>
                  </span>
                  <span className="font-medium">{rupees(i.line_total_paise)}</span>
                </li>
              ))}
            </ul>
            <dl className="space-y-1 border-t pt-3">
              {(
                [
                  ["Subtotal", order.subtotal_paise],
                  [`Discount${order.coupon_code ? ` (${order.coupon_code})` : ""}`, -order.discount_paise],
                  ["Shipping", order.shipping_paise],
                  [order.prices_include_tax ? "GST (included)" : "GST", order.tax_paise],
                ] as const
              ).map(([label, v]) => (
                <div key={label} className="flex justify-between text-muted-foreground">
                  <dt>{label}</dt>
                  <dd>{rupees(v, { decimals: true })}</dd>
                </div>
              ))}
              <div className="flex justify-between font-semibold">
                <dt>Total</dt>
                <dd>{rupees(order.total_paise, { decimals: true })}</dd>
              </div>
            </dl>
          </Card>

          <Card title="Shipments">
            {order.shipments.length === 0 ? (
              <p className="text-muted-foreground">Not shipped yet.</p>
            ) : (
              order.shipments.map((s) => (
                <div key={s.id} className="space-y-2 rounded-lg border p-3">
                  <p className="flex flex-wrap items-center gap-2">
                    <Badge variant="secondary">{s.is_return ? "Return" : "Forward"}</Badge>
                    <span className="font-medium">{s.courier ?? s.provider}</span>
                    {s.awb && <span className="font-mono text-xs">AWB {s.awb}</span>}
                    <span className="ml-auto">{titleCase(s.status)}</span>
                  </p>
                  {s.label_url && (
                    <a href={s.label_url} target="_blank" rel="noreferrer" className="text-brand underline">
                      Download label
                    </a>
                  )}
                  {s.events.length > 0 && (
                    <ol className="border-l pl-3 text-xs text-muted-foreground">
                      {[...s.events].reverse().slice(0, 8).map((e, i) => (
                        <li key={i}>
                          {formatDateTime(e.occurred_at)} · {e.raw_status}
                          {e.location && ` · ${e.location}`}
                        </li>
                      ))}
                    </ol>
                  )}
                </div>
              ))
            )}
          </Card>

          <Card title="Timeline">
            <ol className="space-y-1 border-l pl-3">
              {order.history.map((h, i) => (
                <li key={i}>
                  <span className="font-medium">{titleCase(h.to_status)}</span>
                  <span className="text-muted-foreground">
                    {" "}
                    · {formatDateTime(h.created_at)}
                    {h.note && ` · ${h.note}`}
                  </span>
                </li>
              ))}
            </ol>
          </Card>
        </div>

        <div className="space-y-6">
          <Card title="Customer">
            <p>
              {order.customer_name}
              <br />
              <a href={`mailto:${order.customer_email}`} className="text-brand underline">
                {order.customer_email}
              </a>
              {order.customer_phone && <span className="block">{order.customer_phone}</span>}
            </p>
            <Link href={`/admin/customers/${order.user_id}`} className="text-brand underline">
              Customer profile
            </Link>
            <p className="border-t pt-3 text-muted-foreground">
              {[a.line1, a.line2, a.landmark, `${a.city}, ${a.state} ${a.postal_code}`].filter(Boolean).join(", ")}
            </p>
            {order.notes && <p className="rounded-md bg-amber-50 p-2">Note: {order.notes}</p>}
          </Card>

          <Card title="Payment">
            {order.payment ? (
              <dl className="space-y-1">
                <div className="flex justify-between">
                  <dt>Status</dt>
                  <dd>{titleCase(order.payment.status)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Method</dt>
                  <dd>{order.payment.method ?? "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt>Gateway ref</dt>
                  <dd className="font-mono text-xs">{order.payment.provider_payment_id ?? order.payment.provider_order_id}</dd>
                </div>
                {order.payment.failed_attempts > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {order.payment.failed_attempts} failed attempt(s): {order.payment.last_error_description}
                  </p>
                )}
              </dl>
            ) : (
              <p className="text-muted-foreground">No payment started.</p>
            )}
          </Card>

          {order.refunds.length > 0 && (
            <Card title="Refunds">
              <ul className="space-y-2">
                {order.refunds.map((r) => (
                  <li key={r.id} className="flex justify-between gap-2">
                    <span>
                      {rupees(r.amount_paise, { decimals: true })} · {r.reason}
                      {r.failure_reason && <span className="block text-xs text-destructive">{r.failure_reason}</span>}
                    </span>
                    <Badge variant={r.status === "PROCESSED" ? "default" : "secondary"}>{titleCase(r.status)}</Badge>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {order.returns.length > 0 && (
            <Card title="Returns">
              {order.returns.map((r) => (
                <p key={r.id}>
                  <Badge variant="secondary">{titleCase(r.status)}</Badge> {r.reason}
                  {r.admin_note && <span className="block text-xs text-muted-foreground">Note: {r.admin_note}</span>}
                </p>
              ))}
            </Card>
          )}
        </div>
      </div>
    </AdminPage>
  )
}

export default function AdminOrderPage(props: PageProps<"/admin/orders/[id]">) {
  return (
    <Suspense fallback={<TableSkeleton rows={10} />}>
      <Order {...props} />
    </Suspense>
  )
}
