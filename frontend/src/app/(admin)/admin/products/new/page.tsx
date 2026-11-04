import { Suspense } from "react"

import { ProductForm } from "@/components/admin/product-form"
import { AdminPage, TableSkeleton } from "@/components/admin/ui"
import { api, unwrap } from "@/lib/api/client"
import { requireStaff } from "@/lib/session"

async function NewProduct() {
  await requireStaff("catalog")
  const client = await api()
  const [categories, collections, attributes] = await Promise.all([
    client.GET("/api/v1/admin/categories").then(unwrap),
    client.GET("/api/v1/admin/collections").then(unwrap),
    client.GET("/api/v1/admin/attributes").then(unwrap),
  ])
  return <ProductForm categories={categories} collections={collections} attributes={attributes} />
}

export default function NewProductPage() {
  return (
    <AdminPage title="New product" description="Saved as a draft unless you set it to Active.">
      <Suspense fallback={<TableSkeleton rows={10} />}>
        <NewProduct />
      </Suspense>
    </AdminPage>
  )
}
