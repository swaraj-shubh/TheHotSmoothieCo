import Image from "next/image"
import Link from "next/link"
import { Suspense } from "react"

import { AdminPage, CursorPager, Empty, TableSkeleton } from "@/components/admin/ui"
import { api, unwrap } from "@/lib/api/client"
import { requireStaff } from "@/lib/session"

async function Media({ searchParams }: PageProps<"/admin/media">) {
  await requireStaff("catalog")
  const sp = await searchParams
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/media", {
      params: { query: { cursor: typeof sp.cursor === "string" ? sp.cursor : undefined, limit: 48 } },
    }),
  )
  if (!page.items.length) return <Empty title="No images yet">Upload images from a product’s page.</Empty>
  return (
    <div className="space-y-4">
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        {page.items.map((m) => (
          <li key={m.id}>
            <Link href={`/admin/products/${m.product_id}`} className="group block space-y-1">
              <div className="relative aspect-[3/4] overflow-hidden rounded-lg bg-muted">
                <Image src={m.thumbnail_url} alt={m.alt_text ?? ""} fill sizes="200px" className="object-cover" />
              </div>
              <p className="truncate text-xs group-hover:underline">{m.product_title}</p>
              <p className="text-xs text-muted-foreground">
                {m.width && m.height ? `${m.width}×${m.height}` : ""} {m.bytes ? `· ${Math.round(m.bytes / 1024)} KB` : ""}
                {!m.alt_text && <span className="text-amber-700"> · no alt text</span>}
              </p>
            </Link>
          </li>
        ))}
      </ul>
      <CursorPager basePath="/admin/media" params={sp} nextCursor={page.next_cursor} />
    </div>
  )
}

export default function MediaPage(props: PageProps<"/admin/media">) {
  return (
    <AdminPage title="Media library" description="Every product image. Uploading and ordering happen on each product's page.">
      <Suspense fallback={<TableSkeleton />}>
        <Media {...props} />
      </Suspense>
    </AdminPage>
  )
}
