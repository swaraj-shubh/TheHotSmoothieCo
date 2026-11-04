import Form from "next/form"
import { Suspense } from "react"

import { AdminPage, BarChart, StatCard, TableSkeleton } from "@/components/admin/ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, ApiError, unwrap } from "@/lib/api/client"
import { rupees } from "@/lib/format"
import { requireStaff } from "@/lib/session"

type CustomerStats = { buyers: number; repeat_buyers: number; repeat_rate: number; orders_per_buyer: number }
const INTERVALS = ["day", "week", "month"] as const
const isDate = (v: unknown): v is string => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v)

async function Report({ searchParams }: PageProps<"/admin/analytics">) {
  await requireStaff("analytics")
  const sp = await searchParams
  const from = isDate(sp.from) ? sp.from : undefined
  const to = isDate(sp.to) ? sp.to : undefined
  const interval = INTERVALS.find((i) => i === sp.interval) ?? "day"
  const c = await api()
  const range = { from, to }
  const [sales, top, customers] = await Promise.all([
    c.GET("/api/v1/admin/analytics/sales", { params: { query: { ...range, interval } } }),
    c.GET("/api/v1/admin/analytics/top-products", { params: { query: { ...range, by: "revenue", limit: 10 } } }),
    c.GET("/api/v1/admin/analytics/customers", { params: { query: range } }),
  ])
  // A range the API rejects (too long for the interval, from > to) comes back as an error, not a crash.
  let series, products, cust
  try {
    ;[series, products, cust] = [unwrap(sales), unwrap(top), unwrap(customers) as CustomerStats]
  } catch (e) {
    if (!(e instanceof ApiError) || e.status !== 422) throw e
    return <p className="rounded-lg bg-destructive/5 p-3 text-sm text-destructive">{e.message}</p>
  }
  const sum = (k: "orders" | "gross_paise" | "discount_paise" | "refunds_paise" | "net_paise") => series.reduce((s, p) => s + p[k], 0)
  const orders = sum("orders")

  return (
    <div className="space-y-6">
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Net revenue" value={rupees(sum("net_paise"))} hint={`${rupees(sum("gross_paise"))} gross · ${rupees(sum("refunds_paise"))} refunded`} />
        <StatCard label="Paid orders" value={orders} hint={`avg ${rupees(orders ? Math.round(sum("gross_paise") / orders) : 0)}`} />
        <StatCard label="Discounts given" value={rupees(sum("discount_paise"))} />
        <StatCard label="Repeat buyers" value={`${Math.round(cust.repeat_rate * 100)}%`} hint={`${cust.repeat_buyers} of ${cust.buyers} · ${cust.orders_per_buyer} orders each`} />
      </section>
      <section className="rounded-xl border bg-card p-5">
        <h2 className="mb-3 font-semibold">Net revenue per {interval}</h2>
        <BarChart data={series.map((p) => ({ label: p.period, value: p.net_paise }))} format={(v) => rupees(v)} />
      </section>
      <section className="rounded-xl border bg-card">
        <h2 className="p-5 pb-0 font-semibold">Top products</h2>
        {products.length === 0 ? (
          <p className="p-5 text-sm text-muted-foreground">No sales in this period.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead className="text-right">Units</TableHead>
                <TableHead className="text-right">Revenue</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {products.map((p) => (
                <TableRow key={p.product_id}>
                  <TableCell>{p.title}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.units}</TableCell>
                  <TableCell className="text-right tabular-nums">{rupees(p.revenue_paise)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  )
}

export default function AnalyticsPage(props: PageProps<"/admin/analytics">) {
  return (
    <AdminPage title="Analytics" description="Paid orders, IST days. Defaults to the last 30 days.">
      <Form action="/admin/analytics" className="flex flex-wrap items-end gap-2 text-sm">
        <label className="space-y-1">
          <span className="block text-muted-foreground">From</span>
          <Input type="date" name="from" className="h-8" />
        </label>
        <label className="space-y-1">
          <span className="block text-muted-foreground">To</span>
          <Input type="date" name="to" className="h-8" />
        </label>
        <label className="space-y-1">
          <span className="block text-muted-foreground">Group by</span>
          <select name="interval" className="h-8 rounded-lg border bg-background px-2">
            {INTERVALS.map((i) => (
              <option key={i}>{i}</option>
            ))}
          </select>
        </label>
        <Button size="sm" variant="outline">
          Apply
        </Button>
      </Form>
      <Suspense fallback={<TableSkeleton rows={8} />}>
        <Report {...props} />
      </Suspense>
    </AdminPage>
  )
}
