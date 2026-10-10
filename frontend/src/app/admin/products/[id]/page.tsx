import Link from "next/link"
import { notFound } from "next/navigation"
import { Suspense } from "react"

import { MediaManager, VariantsEditor } from "@/components/admin/product-extras"
import { ProductForm } from "@/components/admin/product-form"
import { AdminPage, TableSkeleton } from "@/components/admin/ui"
import { Button } from "@/components/ui/button"
import { api, unwrap, unwrapOrNull } from "@/lib/api/client"
import { requireStaff } from "@/lib/session"

async function EditProduct({ params, searchParams }: PageProps<"/admin/products/[id]">) {
  await requireStaff("catalog")
  const [{ id }, sp] = await Promise.all([params, searchParams])
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound()
  const client = await api()
  const [product, categories, collections, attributes] = await Promise.all([
    client.GET("/api/v1/admin/products/{product_id}", { params: { path: { product_id: id } } }).then(unwrapOrNull),
    client.GET("/api/v1/admin/categories").then(unwrap),
    client.GET("/api/v1/admin/collections").then(unwrap),
    client.GET("/api/v1/admin/attributes").then(unwrap),
  ])
  if (!product) notFound()
  return (
    <AdminPage
      title={product.title}
      description={sp.created ? "Product created." : `/${product.slug}`}
      actions={
        product.status === "ACTIVE" && (
          <Button asChild variant="outline">
            <Link href={`/product/${product.slug}`} target="_blank">
              View in store ↗
            </Link>
          </Button>
        )
      }
    >
      <ProductForm product={product} categories={categories} collections={collections} attributes={attributes} />
      <VariantsEditor product={product} attributes={attributes} />
      <MediaManager product={product} />
    </AdminPage>
  )
}

export default function EditProductPage(props: PageProps<"/admin/products/[id]">) {
  return (
    <Suspense fallback={<TableSkeleton rows={12} />}>
      <EditProduct {...props} />
    </Suspense>
  )
}
