import Form from "next/form"
import Link from "next/link"
import { Suspense } from "react"

import { StockAdjust } from "@/components/admin/stock-adjust"
import { AdminPage, CursorPager, Empty, LinkTabs, TableSkeleton } from "@/components/admin/ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, unwrap } from "@/lib/api/client"
import { formatDateTime, titleCase } from "@/lib/format"
import { requireStaff } from "@/lib/session"

async function History({ variantId, sku }: { variantId: string; sku: string }) {
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/inventory/{variant_id}/history", { params: { path: { variant_id: variantId }, query: { limit: 50 } } }),
  )
  return (
    <ol className="space-y-3 px-4 text-sm">
      {page.items.map((t) => (
        <li key={t.id} className="border-b pb-2">
          <p className="flex justify-between font-medium">
            <span>{titleCase(t.type)}</span>
            <span className="tabular-nums">
              {t.on_hand_delta ? (t.on_hand_delta > 0 ? `+${t.on_hand_delta}` : t.on_hand_delta) : ""}
              {t.reserved_delta ? ` (held ${t.reserved_delta > 0 ? "+" : ""}${t.reserved_delta})` : ""}
            </span>
          </p>
          <p className="text-xs text-muted-foreground">
            {formatDateTime(t.created_at)} · on hand {t.on_hand_after}, held {t.reserved_after}
            {t.reason && ` · ${t.reason}`}
          </p>
        </li>
      ))}
      {page.items.length === 0 && <li className="text-muted-foreground">No movements for {sku}.</li>}
    </ol>
  )
}

async function Inventory({ searchParams }: PageProps<"/admin/inventory">) {
  await requireStaff("inventory")
  const sp = await searchParams
  const low = sp.low_stock === "1"
  const q = typeof sp.q === "string" ? sp.q : undefined
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/inventory", {
      params: { query: { low_stock: low, q, cursor: typeof sp.cursor === "string" ? sp.cursor : undefined, limit: 50 } },
    }),
  )
  const historyFor = typeof sp.history === "string" ? page.items.find((r) => r.variant_id === sp.history) : undefined
  return (
    <div className="space-y-4">
      <LinkTabs
        active={low ? "low" : "all"}
        tabs={[
          { key: "all", label: "All stock", href: "/admin/inventory" },
          { key: "low", label: "Low stock", href: "/admin/inventory?low_stock=1" },
        ]}
      />
      <Form action="/admin/inventory" className="flex max-w-sm gap-2">
        {low && <input type="hidden" name="low_stock" value="1" />}
        <Input name="q" defaultValue={q} placeholder="SKU starts with…" aria-label="Search SKU" />
        <Button variant="outline">Search</Button>
      </Form>
      {page.items.length === 0 ? (
        <Empty title={low ? "Nothing is running low" : "No stock records"} />
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>SKU</TableHead>
                <TableHead>Product</TableHead>
                <TableHead className="text-right">On hand</TableHead>
                <TableHead className="text-right">Held</TableHead>
                <TableHead className="text-right">Available</TableHead>
                <TableHead className="text-right">Sold</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((r) => (
                <TableRow key={r.variant_id}>
                  <TableCell className="font-mono text-xs">{r.sku}</TableCell>
                  <TableCell>
                    <Link href={`/admin/products/${r.product_id}`} className="hover:underline">
                      {r.product_title}
                    </Link>
                    <span className="text-muted-foreground"> · {r.variant_title}</span>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{r.on_hand}</TableCell>
                  <TableCell className="text-right tabular-nums">{r.reserved}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {r.available}{" "}
                    {r.available <= 0 ? <Badge variant="destructive">Out</Badge> : r.low_stock && <Badge className="bg-amber-500">Low</Badge>}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{r.sold}</TableCell>
                  <TableCell className="flex justify-end gap-2">
                    <StockAdjust row={r} />
                    <Button asChild size="sm" variant="ghost">
                      <Link href={`?${new URLSearchParams({ ...(low ? { low_stock: "1" } : {}), ...(q ? { q } : {}), history: r.variant_id })}`} scroll={false}>
                        History
                      </Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <CursorPager basePath="/admin/inventory" params={sp} nextCursor={page.next_cursor} />
      {historyFor && (
        <Sheet open>
          <SheetContent className="overflow-y-auto">
            <SheetHeader>
              <SheetTitle>History · {historyFor.sku}</SheetTitle>
              <Link href={`/admin/inventory${low ? "?low_stock=1" : ""}`} className="text-sm text-brand underline" scroll={false}>
                Close
              </Link>
            </SheetHeader>
            <Suspense fallback={<TableSkeleton rows={4} />}>
              <History variantId={historyFor.variant_id} sku={historyFor.sku} />
            </Suspense>
          </SheetContent>
        </Sheet>
      )}
    </div>
  )
}

export default function InventoryPage(props: PageProps<"/admin/inventory">) {
  return (
    <AdminPage title="Inventory" description="Available = on hand − held by unpaid checkouts. Every change is logged.">
      <Suspense fallback={<TableSkeleton />}>
        <Inventory {...props} />
      </Suspense>
    </AdminPage>
  )
}
