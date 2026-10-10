import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { OrderStatusBadge } from "@/components/account/order-status"
import { Button } from "@/components/ui/button"
import { api, unwrap } from "@/lib/api/client"
import { formatDate, rupees } from "@/lib/format"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Your orders", robots: { index: false } }

async function Orders({ searchParams }: PageProps<"/account/orders">) {
  await requireUser("/account/orders")
  const { cursor } = await searchParams
  const page = unwrap(
    await (await api()).GET("/api/v1/orders", {
      params: { query: { cursor: typeof cursor === "string" ? cursor : undefined, limit: 20 } },
    }),
  )
  if (!page.items.length && !cursor) {
    return (
      <div className=" border border-dashed py-16 text-center">
        <p className="text-muted-foreground">You haven’t placed any orders yet.</p>
        <Button asChild className="mt-4">
          <Link href="/shop">Find something you love</Link>
        </Button>
      </div>
    )
  }
  return (
    <div className="space-y-6">
      <ul className="divide-y border">
        {page.items.map((o) => (
          <li key={o.id}>
            <Link href={`/account/orders/${o.id}`} className="flex flex-wrap items-center gap-x-6 gap-y-2 p-5 hover:bg-muted/50">
              <span className="font-medium">{o.number}</span>
              <span className="text-sm text-muted-foreground">{formatDate(o.created_at)}</span>
              <span className="text-sm text-muted-foreground">
                {o.item_count} item{o.item_count === 1 ? "" : "s"}
              </span>
              <OrderStatusBadge status={o.status} />
              <span className="ml-auto font-medium">{rupees(o.total_paise)}</span>
            </Link>
          </li>
        ))}
      </ul>
      <div className="flex justify-center gap-3">
        {cursor && (
          <Button asChild variant="outline">
            <Link href="/account/orders">← Most recent</Link>
          </Button>
        )}
        {page.next_cursor && (
          <Button asChild variant="outline">
            <Link href={`/account/orders?cursor=${encodeURIComponent(page.next_cursor)}`}>Older orders →</Link>
          </Button>
        )}
      </div>
    </div>
  )
}

export default function OrdersPage(props: PageProps<"/account/orders">) {
  return (
    <>
      <h1 className="mb-6 font-display text-5xl leading-none tracking-tight">Your orders</h1>
      <Suspense fallback={<div className="h-64 animate-pulse bg-muted" />}>
        <Orders {...props} />
      </Suspense>
    </>
  )
}
