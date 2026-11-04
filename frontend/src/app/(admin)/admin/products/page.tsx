import Form from "next/form"
import Link from "next/link"
import { Suspense } from "react"

import { CsvImport, PriceRange } from "@/components/admin/product-extras"
import { AdminPage, CursorPager, Empty, LinkTabs, TableSkeleton } from "@/components/admin/ui"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { api, unwrap } from "@/lib/api/client"
import { formatDate, titleCase } from "@/lib/format"
import { requireStaff } from "@/lib/session"

const STATUSES = ["ACTIVE", "DRAFT", "ARCHIVED"] as const

async function Products({ searchParams }: PageProps<"/admin/products">) {
  await requireStaff("catalog")
  const sp = await searchParams
  const status = STATUSES.find((s) => s === sp.status)
  const q = typeof sp.q === "string" ? sp.q : undefined
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/products", {
      params: { query: { status, q, cursor: typeof sp.cursor === "string" ? sp.cursor : undefined, limit: 50 } },
    }),
  )
  return (
    <div className="space-y-4">
      <LinkTabs
        active={status ?? "all"}
        tabs={[{ key: "all", label: "All", href: "/admin/products" }, ...STATUSES.map((s) => ({ key: s, label: titleCase(s), href: `/admin/products?status=${s}` }))]}
      />
      <Form action="/admin/products" className="flex max-w-md gap-2">
        {status && <input type="hidden" name="status" value={status} />}
        <Input name="q" defaultValue={q} placeholder="Search title, slug or SKU" aria-label="Search products" />
        <Button variant="outline">Search</Button>
      </Form>
      {page.items.length === 0 ? (
        <Empty title={q ? `No products match “${q}”` : "No products yet"}>
          <Link href="/admin/products/new" className="text-brand underline">
            Create your first product
          </Link>
        </Empty>
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((p) => (
                <TableRow key={p.id}>
                  <TableCell>
                    <Link href={`/admin/products/${p.id}`} className="font-medium hover:underline">
                      {p.title}
                    </Link>
                    <p className="text-xs text-muted-foreground">/{p.slug}</p>
                  </TableCell>
                  <TableCell>
                    <Badge variant={p.status === "ACTIVE" ? "default" : "secondary"}>{titleCase(p.status)}</Badge>
                  </TableCell>
                  <TableCell>
                    <PriceRange min={p.min_price_paise} max={p.max_price_paise} />
                  </TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(p.updated_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <CursorPager basePath="/admin/products" params={sp} nextCursor={page.next_cursor} />
    </div>
  )
}

export default function ProductsPage(props: PageProps<"/admin/products">) {
  return (
    <AdminPage
      title="Products"
      actions={
        <>
          <Button asChild variant="outline">
            <a href="/admin/products/export" download>
              Export CSV
            </a>
          </Button>
          <Button asChild>
            <Link href="/admin/products/new">New product</Link>
          </Button>
        </>
      }
    >
      <CsvImport />
      <Suspense fallback={<TableSkeleton />}>
        <Products {...props} />
      </Suspense>
    </AdminPage>
  )
}
