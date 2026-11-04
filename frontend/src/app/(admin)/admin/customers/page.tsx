import Form from "next/form"
import Link from "next/link"
import { Suspense } from "react"

import { AdminPage, CursorPager, Empty, TableSkeleton } from "@/components/admin/ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, unwrap } from "@/lib/api/client"
import { formatDate, rupees } from "@/lib/format"
import { requireStaff } from "@/lib/session"

async function Customers({ searchParams }: PageProps<"/admin/customers">) {
  await requireStaff("customers")
  const sp = await searchParams
  const q = typeof sp.q === "string" ? sp.q.trim() : undefined
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/customers", {
      params: { query: { q: q || undefined, cursor: typeof sp.cursor === "string" ? sp.cursor : undefined, limit: 50 } },
    }),
  )
  return (
    <div className="space-y-4">
      <Form action="/admin/customers" className="flex max-w-md gap-2">
        <Input name="q" defaultValue={q} placeholder="Email, name or phone" aria-label="Search customers" />
        <Button variant="outline">Search</Button>
      </Form>
      {page.items.length === 0 ? (
        <Empty title={q ? `No customers match “${q}”` : "No customers yet"} />
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer</TableHead>
                <TableHead>Joined</TableHead>
                <TableHead className="text-right">Orders</TableHead>
                <TableHead className="text-right">Spent</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>
                    <Link href={`/admin/customers/${c.id}`} className="font-medium hover:underline">
                      {c.full_name}
                    </Link>
                    <p className="text-xs text-muted-foreground">{c.email}</p>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(c.created_at)}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.order_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{rupees(c.total_spent_paise)}</TableCell>
                  <TableCell>{c.is_active ? <Badge variant="secondary">Active</Badge> : <Badge variant="destructive">Deactivated</Badge>}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <CursorPager basePath="/admin/customers" params={sp} nextCursor={page.next_cursor} />
    </div>
  )
}

export default function CustomersPage(props: PageProps<"/admin/customers">) {
  return (
    <AdminPage title="Customers">
      <Suspense fallback={<TableSkeleton />}>
        <Customers {...props} />
      </Suspense>
    </AdminPage>
  )
}
