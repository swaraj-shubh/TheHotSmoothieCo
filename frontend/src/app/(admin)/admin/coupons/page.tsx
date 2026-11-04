import { Suspense } from "react"

import { setCouponActive } from "@/app/actions/admin"
import { ActionButton } from "@/components/admin/action-button"
import { CouponCreate } from "@/components/admin/editors"
import { AdminPage, CursorPager, Empty, TableSkeleton } from "@/components/admin/ui"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, unwrap } from "@/lib/api/client"
import type { CouponOut } from "@/lib/api/types"
import { formatDate, rupees } from "@/lib/format"
import { requireStaff } from "@/lib/session"

function describe(c: CouponOut) {
  const off = c.discount_type === "PERCENT" ? `${c.value}% off` : `${rupees(c.value)} off`
  return [
    off,
    c.max_discount_paise && `up to ${rupees(c.max_discount_paise)}`,
    c.min_subtotal_paise > 0 && `on ${rupees(c.min_subtotal_paise)}+`,
    c.first_order_only && "first order",
    c.per_user_limit && `${c.per_user_limit}/customer`,
  ]
    .filter(Boolean)
    .join(" · ")
}

async function Coupons({ searchParams }: PageProps<"/admin/coupons">) {
  await requireStaff("marketing")
  const sp = await searchParams
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/coupons", {
      params: { query: { cursor: typeof sp.cursor === "string" ? sp.cursor : undefined, limit: 50 } },
    }),
  )
  if (page.items.length === 0) return <Empty title="No coupons yet" />
  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Discount</TableHead>
              <TableHead>Valid</TableHead>
              <TableHead className="text-right">Used</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {page.items.map((c) => (
              <TableRow key={c.id}>
                <TableCell>
                  <span className="font-mono font-medium">{c.code}</span>
                  {c.description && <p className="text-xs text-muted-foreground">{c.description}</p>}
                </TableCell>
                <TableCell className="text-sm">{describe(c)}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {c.starts_at ? formatDate(c.starts_at) : "Now"} – {c.ends_at ? formatDate(c.ends_at) : "no end"}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {c.times_used}
                  {c.usage_limit ? ` / ${c.usage_limit}` : ""}
                </TableCell>
                <TableCell className="text-right">
                  {c.is_active ? <Badge>Active</Badge> : <Badge variant="secondary">Off</Badge>}{" "}
                  <ActionButton size="sm" variant="ghost" run={setCouponActive.bind(null, c.id, !c.is_active)}>
                    {c.is_active ? "Disable" : "Enable"}
                  </ActionButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <CursorPager basePath="/admin/coupons" params={sp} nextCursor={page.next_cursor} />
    </div>
  )
}

export default function CouponsPage(props: PageProps<"/admin/coupons">) {
  return (
    <AdminPage title="Coupons" actions={<CouponCreate />}>
      <Suspense fallback={<TableSkeleton />}>
        <Coupons {...props} />
      </Suspense>
    </AdminPage>
  )
}
