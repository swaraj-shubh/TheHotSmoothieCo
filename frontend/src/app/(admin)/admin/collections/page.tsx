import { Suspense } from "react"

import { TaxonomyManager } from "@/components/admin/taxonomy"
import { AdminPage, TableSkeleton } from "@/components/admin/ui"
import { api, unwrap } from "@/lib/api/client"
import { requireStaff } from "@/lib/session"

async function Collections() {
  await requireStaff("catalog")
  return <TaxonomyManager kind="collection" items={unwrap(await (await api()).GET("/api/v1/admin/collections"))} />
}

export default function CollectionsPage() {
  return (
    <AdminPage title="Collections" description="Curated groups like “Monsoon Moods” or “Bestsellers”. Assign products on the product page.">
      <Suspense fallback={<TableSkeleton />}>
        <Collections />
      </Suspense>
    </AdminPage>
  )
}
