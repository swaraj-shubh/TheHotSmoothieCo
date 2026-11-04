import Form from "next/form"
import Link from "next/link"
import { Suspense } from "react"

import { OrderStatusBadge } from "@/components/account/order-status"
import { AdminPage, CursorPager, Empty, LinkTabs, TableSkeleton } from "@/components/admin/ui"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, unwrap } from "@/lib/api/client"
import type { paths } from "@/lib/api/schema"
import { formatDateTime, rupees } from "@/lib/format"
import { requireStaff } from "@/lib/session"

type OrderStatus = NonNullable<NonNullable<paths["/api/v1/admin/orders"]["get"]["parameters"]["query"]>["status"]>

const TABS = [
  ["all", "All"],
  ["CONFIRMED", "To fulfil"],
  ["PROCESSING", "Processing"],
  ["PACKED", "Packed"],
  ["SHIPPED", "Shipped"],
  ["RETURN_REQUESTED", "Returns"],
  ["REFUND_PENDING", "Refunds"],
  ["PENDING_PAYMENT", "Unpaid"],
  ["CANCELLED", "Cancelled"],
] as const

async function Orders({ searchParams }: PageProps<"/admin/orders">) {
  await requireStaff("orders")
  const sp = await searchParams
  const status = TABS.find(([k]) => k !== "all" && k === sp.status)?.[0]
  const q = typeof sp.q === "string" ? sp.q.trim() : undefined
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/orders", {
      params: {
        query: {
          status: status as OrderStatus | undefined,
          q: q || undefined,
          cursor: typeof sp.cursor === "string" ? sp.cursor : undefined,
          limit: 50,
        },
      },
    }),
  )
  return (
    <div className="space-y-4">
      <LinkTabs active={status ?? "all"} tabs={TABS.map(([key, label]) => ({ key, label, href: key === "all" ? "/admin/orders" : `/admin/orders?status=${key}` }))} />
      <Form action="/admin/orders" className="flex max-w-md gap-2">
        <Input name="q" defaultValue={q} placeholder="Order number or customer email" aria-label="Find order" />
        <Button variant="outline">Find</Button>
      </Form>
      {page.items.length === 0 ? (
        <Empty title="No orders here" />
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Order</TableHead>
                <TableHead>Customer</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Placed</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((o) => (
                <TableRow key={o.id}>
                  <TableCell>
                    <Link href={`/admin/orders/${o.id}`} className="font-medium hover:underline">
                      {o.number}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {o.customer_name}
                    <p className="text-xs text-muted-foreground">{o.customer_email}</p>
                  </TableCell>
                  <TableCell>
                    <OrderStatusBadge status={o.status} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDateTime(o.created_at)}</TableCell>
                  <TableCell className="text-right font-medium">{rupees(o.total_paise)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <CursorPager basePath="/admin/orders" params={sp} nextCursor={page.next_cursor} />
    </div>
  )
}

export default function OrdersPage(props: PageProps<"/admin/orders">) {
  return (
    <AdminPage title="Orders">
      <Suspense fallback={<TableSkeleton />}>
        <Orders {...props} />
      </Suspense>
    </AdminPage>
  )
}
