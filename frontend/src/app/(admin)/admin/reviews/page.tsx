import Image from "next/image"
import Link from "next/link"
import { Suspense } from "react"

import { ActionButton } from "@/components/admin/action-button"
import { AdminPage, CursorPager, Empty, LinkTabs, TableSkeleton } from "@/components/admin/ui"
import { Badge } from "@/components/ui/badge"
import { moderateReview } from "@/app/actions/admin"
import { api, unwrap } from "@/lib/api/client"
import { formatDateTime } from "@/lib/format"
import { requireStaff } from "@/lib/session"

const TABS = [
  ["PENDING", "To moderate"],
  ["APPROVED", "Published"],
  ["REJECTED", "Rejected"],
] as const

async function Reviews({ searchParams }: PageProps<"/admin/reviews">) {
  await requireStaff("reviews")
  const sp = await searchParams
  const status = TABS.find(([k]) => k === sp.status)?.[0] ?? "PENDING"
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/reviews", {
      params: { query: { status, cursor: typeof sp.cursor === "string" ? sp.cursor : undefined, limit: 30 } },
    }),
  )
  return (
    <div className="space-y-4">
      <LinkTabs active={status} tabs={TABS.map(([key, label]) => ({ key, label, href: `/admin/reviews?status=${key}` }))} />
      {page.items.length === 0 ? (
        <Empty title={status === "PENDING" ? "Nothing waiting. Nice." : "No reviews here"} />
      ) : (
        <ul className="space-y-3">
          {page.items.map((r) => (
            <li key={r.id} className="space-y-2 rounded-xl border bg-card p-4 text-sm">
              <p className="flex flex-wrap items-center gap-2">
                <span className="text-amber-500" aria-label={`${r.rating} out of 5`}>
                  {"★".repeat(r.rating)}
                  <span className="text-muted-foreground/40">{"★".repeat(5 - r.rating)}</span>
                </span>
                {r.verified_purchase && <Badge variant="secondary">Verified buyer</Badge>}
                <span className="text-muted-foreground">
                  on{" "}
                  <Link href={`/product/${r.product_slug}`} target="_blank" className="text-foreground hover:underline">
                    {r.product_title}
                  </Link>{" "}
                  · {r.author_email} · {formatDateTime(r.created_at)}
                </span>
              </p>
              {r.title && <p className="font-medium">{r.title}</p>}
              {r.body && <p className="whitespace-pre-line text-muted-foreground">{r.body}</p>}
              {r.media.length > 0 && (
                <div className="flex gap-2">
                  {r.media.map((m) => (
                    <a key={m.id} href={m.url} target="_blank" rel="noreferrer" className="relative size-20 overflow-hidden rounded-md bg-muted">
                      <Image src={m.thumbnail_url} alt="Customer photo" fill sizes="80px" className="object-cover" />
                    </a>
                  ))}
                </div>
              )}
              {r.moderation_note && <p className="text-xs text-muted-foreground">Note: {r.moderation_note}</p>}
              <div className="flex gap-2">
                {r.status !== "APPROVED" && (
                  <ActionButton size="sm" run={moderateReview.bind(null, r.id, "approve", undefined)}>
                    Publish
                  </ActionButton>
                )}
                {r.status !== "REJECTED" && (
                  <ActionButton
                    size="sm"
                    variant="outline"
                    run={moderateReview.bind(null, r.id, "reject", undefined)}
                    confirm={{ title: "Reject this review?", description: "It's hidden from the store; the customer can edit and resubmit.", action: "Reject" }}
                  >
                    {r.status === "APPROVED" ? "Unpublish" : "Reject"}
                  </ActionButton>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      <CursorPager basePath="/admin/reviews" params={sp} nextCursor={page.next_cursor} />
    </div>
  )
}

export default function ReviewsPage(props: PageProps<"/admin/reviews">) {
  return (
    <AdminPage title="Reviews" description="Every review and photo is checked before it appears in the store.">
      <Suspense fallback={<TableSkeleton />}>
        <Reviews {...props} />
      </Suspense>
    </AdminPage>
  )
}
