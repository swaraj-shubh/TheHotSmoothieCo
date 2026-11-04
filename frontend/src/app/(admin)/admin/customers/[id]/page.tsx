import Link from "next/link"
import { notFound } from "next/navigation"
import { Suspense } from "react"

import { OrderStatusBadge } from "@/components/account/order-status"
import { CustomerStatus } from "@/components/admin/customer-status"
import { AdminPage, StatCard, TableSkeleton } from "@/components/admin/ui"
import { can } from "@/lib/admin-access"
import { api, unwrapOrNull } from "@/lib/api/client"
import { formatDate, formatDateTime, rupees } from "@/lib/format"
import { requireStaff } from "@/lib/session"

async function Customer({ params }: PageProps<"/admin/customers/[id]">) {
  const user = await requireStaff("customers")
  const { id } = await params
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound()
  const c = unwrapOrNull(await (await api()).GET("/api/v1/admin/customers/{user_id}", { params: { path: { user_id: id } } }))
  if (!c) notFound()
  return (
    <AdminPage
      title={c.full_name}
      description={`${c.email}${c.phone ? ` · ${c.phone}` : ""} · joined ${formatDate(c.created_at)}`}
      actions={can(user.roles, "customersWrite") && <CustomerStatus userId={c.id} isActive={c.is_active} />}
    >
      <div className="grid gap-4 sm:grid-cols-4">
        <StatCard label="Paid orders" value={c.order_count} />
        <StatCard label="Lifetime spend" value={rupees(c.total_spent_paise)} />
        <StatCard label="Email" value={c.email_verified ? "Verified" : "Unverified"} />
        <StatCard label="Last login" value={c.last_login_at ? formatDate(c.last_login_at) : "—"} />
      </div>
      <section className="space-y-2 rounded-xl border bg-card p-5 text-sm">
        <h2 className="font-semibold">Recent orders</h2>
        {c.recent_orders.length === 0 ? (
          <p className="text-muted-foreground">No orders yet.</p>
        ) : (
          <ul className="divide-y">
            {c.recent_orders.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-4 py-2">
                <Link href={`/admin/orders/${o.id}`} className="font-medium hover:underline">
                  {o.number}
                </Link>
                <span className="text-muted-foreground">{formatDateTime(o.created_at)}</span>
                <OrderStatusBadge status={o.status} />
                <span className="ml-auto">{rupees(o.total_paise)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
      <section className="space-y-2 rounded-xl border bg-card p-5 text-sm">
        <h2 className="font-semibold">Addresses</h2>
        {c.addresses.length === 0 && <p className="text-muted-foreground">None saved.</p>}
        {c.addresses.map((a) => (
          <p key={a.id}>
            {a.full_name}, {a.line1}, {a.city}, {a.state} {a.postal_code} · {a.phone}
          </p>
        ))}
      </section>
    </AdminPage>
  )
}

export default function CustomerPage(props: PageProps<"/admin/customers/[id]">) {
  return (
    <Suspense fallback={<TableSkeleton rows={8} />}>
      <Customer {...props} />
    </Suspense>
  )
}
