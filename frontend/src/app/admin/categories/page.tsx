import { Suspense } from "react"

import { AttributesManager, TaxonomyManager } from "@/components/admin/taxonomy"
import { AdminPage, TableSkeleton } from "@/components/admin/ui"
import { api, unwrap } from "@/lib/api/client"
import { requireStaff } from "@/lib/session"

async function Categories() {
  await requireStaff("catalog")
  const client = await api()
  const [categories, attributes] = await Promise.all([
    client.GET("/api/v1/admin/categories").then(unwrap),
    client.GET("/api/v1/admin/attributes").then(unwrap),
  ])
  return (
    <div className="space-y-8">
      <TaxonomyManager kind="category" items={categories} />
      <AttributesManager attributes={attributes} />
    </div>
  )
}

export default function CategoriesPage() {
  return (
    <AdminPage title="Categories" description="Categories organise the shop; product options (size, frame…) power filters.">
      <Suspense fallback={<TableSkeleton />}>
        <Categories />
      </Suspense>
    </AdminPage>
  )
}
