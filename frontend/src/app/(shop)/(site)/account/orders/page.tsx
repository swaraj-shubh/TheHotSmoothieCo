import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { Empty } from "@/components/sf/bits"
import { api, unwrap } from "@/lib/api/client"
import { formatDate, money, orderLabel } from "@/lib/format"
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
      <Empty title={<p className="t-head">No orders yet. Your walls are still safe.</p>}>
        <Link className="btn" href="/shop">
          [ Shop the drop ]
        </Link>
      </Empty>
    )
  }
  return (
    <>
      <div>
        {page.items.map((o) => (
          <Link key={o.id} className="order-row" href={`/account/orders/${o.id}`}>
            <b>{o.number}</b>
            <span className="t-cap muted">{formatDate(o.created_at)}</span>
            <span className="t-cap muted">
              {o.item_count} item{o.item_count === 1 ? "" : "s"}
            </span>
            <span className="chip chip--outline">{orderLabel(o.status)}</span>
            <span className="t-price">{money(o.total_paise)}</span>
          </Link>
        ))}
      </div>
      <div style={{ display: "flex", gap: 20, justifyContent: "center" }}>
        {cursor && (
          <Link className="btn-link" href="/account/orders">
            Most recent
          </Link>
        )}
        {page.next_cursor && (
          <Link className="btn-link" href={`/account/orders?cursor=${encodeURIComponent(page.next_cursor)}`}>
            Older orders <span aria-hidden="true">→</span>
          </Link>
        )}
      </div>
    </>
  )
}

export default function OrdersPage(props: PageProps<"/account/orders">) {
  return (
    <div style={{ display: "grid", gap: 40 }}>
      <h1 className="t-display">Your orders.</h1>
      <Suspense fallback={null}>
        <Orders {...props} />
      </Suspense>
    </div>
  )
}
