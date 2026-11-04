import { Suspense } from "react"

import { AdminPage, BarChart, StatCard, TableSkeleton } from "@/components/admin/ui"
import { can } from "@/lib/admin-access"
import { api, unwrap } from "@/lib/api/client"
import { rupees } from "@/lib/format"
import { requireStaff } from "@/lib/session"

type Revenue = { orders: number; gross_paise: number; refunds_paise: number; net_paise: number }
type Dashboard = {
  revenue: { today: Revenue; last_7_days: Revenue; last_30_days: Revenue }
  needs_attention: Record<string, number>
  inventory: { low_stock_variants: number; out_of_stock_variants: number }
  customers: { total: number; new_last_30_days: number }
  products: Record<string, number>
  generated_at: string
}

async function SalesChart() {
  const series = unwrap(await (await api()).GET("/api/v1/admin/analytics/sales", { params: { query: { interval: "day" } } }))
  return (
    <section className="rounded-xl border bg-card p-5">
      <h2 className="mb-3 font-semibold">Net revenue, last 30 days</h2>
      <BarChart data={series.map((p) => ({ label: p.period.slice(5), value: p.net_paise }))} format={(v) => rupees(v)} />
    </section>
  )
}

async function Overview() {
  const user = await requireStaff()
  const d = unwrap(await (await api()).GET("/api/v1/admin/dashboard")) as unknown as Dashboard
  const n = d.needs_attention
  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-3">
        {(
          [
            ["Today", d.revenue.today],
            ["Last 7 days", d.revenue.last_7_days],
            ["Last 30 days", d.revenue.last_30_days],
          ] as const
        ).map(([label, r]) => (
          <StatCard
            key={label}
            label={`Net revenue · ${label}`}
            value={rupees(r.net_paise)}
            hint={`${r.orders} paid orders${r.refunds_paise ? ` · ${rupees(r.refunds_paise)} refunded` : ""}`}
          />
        ))}
      </section>

      <section>
        <h2 className="mb-3 font-semibold">Needs attention</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="To fulfil" value={n.to_fulfil} href="/admin/orders?status=CONFIRMED" tone={n.to_fulfil ? "warn" : "default"} />
          <StatCard label="Awaiting pickup" value={n.awaiting_pickup} href="/admin/orders?status=PACKED" />
          <StatCard label="Return requests" value={n.return_requests} href="/admin/orders?status=RETURN_REQUESTED" tone={n.return_requests ? "warn" : "default"} />
          <StatCard label="Refunds pending" value={n.refunds_pending} hint={rupees(n.refunds_pending_paise)} href="/admin/orders?status=REFUND_PENDING" />
          <StatCard label="Reviews to moderate" value={n.reviews_to_moderate} href="/admin/reviews" />
          <StatCard
            label="Low / out of stock"
            value={`${d.inventory.low_stock_variants} / ${d.inventory.out_of_stock_variants}`}
            href="/admin/inventory?low_stock=1"
            tone={d.inventory.out_of_stock_variants ? "warn" : "default"}
          />
          <StatCard label="Failed emails" value={n.failed_notifications} href="/admin/notifications?status=FAILED" tone={n.failed_notifications ? "danger" : "default"} />
          <StatCard label="Failed webhooks" value={n.failed_webhooks} tone={n.failed_webhooks ? "danger" : "default"} hint="Check API logs / Sentry" />
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Customers" value={d.customers.total} hint={`${d.customers.new_last_30_days} new in 30 days`} href="/admin/customers" />
        <StatCard label="Live products" value={d.products.active ?? 0} hint={`${d.products.draft ?? 0} drafts`} href="/admin/products" />
        <StatCard label="Archived products" value={d.products.archived ?? 0} href="/admin/products?status=ARCHIVED" />
      </section>

      {can(user.roles, "analytics") && (
        <Suspense fallback={<TableSkeleton rows={4} />}>
          <SalesChart />
        </Suspense>
      )}
      <p className="text-xs text-muted-foreground">Figures refresh every minute.</p>
    </div>
  )
}

export default function DashboardPage() {
  return (
    <AdminPage title="Dashboard">
      <Suspense fallback={<TableSkeleton rows={8} />}>
        <Overview />
      </Suspense>
    </AdminPage>
  )
}
