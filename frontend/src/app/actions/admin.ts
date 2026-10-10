"use server"

import { randomUUID } from "node:crypto"

import { refresh, revalidateTag } from "next/cache"
import { redirect } from "next/navigation"

import { action, type ActionResult } from "@/lib/action-result"
import { api, apiUpload, unwrap } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"
import { toPaise } from "@/lib/format"

type S = components["schemas"]

/** Every admin write: call the API (which re-checks the role), refresh the admin view, and
 *  expire the storefront caches the change affects. */
async function write<T>(fn: (client: Awaited<ReturnType<typeof api>>) => Promise<T>, tags: string[] = [], message?: string) {
  return action(async () => {
    const result = await fn(await api())
    for (const tag of tags) revalidateTag(tag, "max")
    refresh()
    return result
  }, message)
}

const str = (form: FormData, k: string) => String(form.get(k) ?? "").trim()
const opt = (form: FormData, k: string) => str(form, k) || null

// ---------- Catalog ----------

export async function createProduct(payload: S["ProductIn"]): Promise<ActionResult<S["AdminProductOut"]>> {
  const result = await write((c) => c.POST("/api/v1/admin/products", { body: payload }).then(unwrap), ["catalog"])
  if (result.ok && result.data) redirect(`/admin/products/${result.data.id}?created=1`)
  return result
}

export async function updateProduct(id: string, patch: S["ProductPatch"]) {
  return write(
    (c) => c.PATCH("/api/v1/admin/products/{product_id}", { params: { path: { product_id: id } }, body: patch }).then(unwrap),
    ["catalog"],
    "Product saved",
  )
}

export async function addVariant(productId: string, variant: S["VariantIn"]) {
  return write(
    (c) =>
      c.POST("/api/v1/admin/products/{product_id}/variants", { params: { path: { product_id: productId } }, body: variant }).then(unwrap),
    ["catalog"],
    "Variant added",
  )
}

export async function updateVariant(productId: string, variantId: string, patch: S["VariantPatch"]) {
  return write(
    (c) =>
      c
        .PATCH("/api/v1/admin/products/{product_id}/variants/{variant_id}", {
          params: { path: { product_id: productId, variant_id: variantId } },
          body: patch,
        })
        .then(unwrap),
    ["catalog"],
    "Variant updated",
  )
}

export async function uploadMedia(productId: string, form: FormData) {
  // Multipart is passed straight through; the API sniffs the bytes and enforces size limits.
  return write(
    () => apiUpload<S["MediaOut"]>(`/api/v1/admin/products/${encodeURIComponent(productId)}/media`, form),
    ["catalog"],
    "Image uploaded",
  )
}

export async function updateMedia(productId: string, mediaId: string, patch: S["MediaPatch"]) {
  return write(
    (c) =>
      c
        .PATCH("/api/v1/admin/products/{product_id}/media/{media_id}", {
          params: { path: { product_id: productId, media_id: mediaId } },
          body: patch,
        })
        .then(unwrap),
    ["catalog"],
    "Image updated",
  )
}

export async function deleteMedia(productId: string, mediaId: string) {
  return write(
    (c) =>
      c
        .DELETE("/api/v1/admin/products/{product_id}/media/{media_id}", { params: { path: { product_id: productId, media_id: mediaId } } })
        .then(unwrap),
    ["catalog"],
    "Image deleted",
  )
}

export async function saveCategory(_: unknown, form: FormData) {
  const id = str(form, "id")
  const body = {
    name: str(form, "name"),
    slug: opt(form, "slug"),
    parent_id: opt(form, "parent_id"),
    description: opt(form, "description"),
    image_url: opt(form, "image_url"),
    sort_order: Number(str(form, "sort_order") || 0),
    is_active: form.get("is_active") === "on",
    seo_title: opt(form, "seo_title"),
    seo_description: opt(form, "seo_description"),
  }
  return write(
    (c) =>
      (id
        ? c.PATCH("/api/v1/admin/categories/{category_id}", { params: { path: { category_id: id } }, body })
        : c.POST("/api/v1/admin/categories", { body })
      ).then(unwrap),
    ["categories", "catalog"],
    "Category saved",
  )
}

export async function deleteCategory(id: string) {
  return write(
    (c) => c.DELETE("/api/v1/admin/categories/{category_id}", { params: { path: { category_id: id } } }).then(unwrap),
    ["categories", "catalog"],
    "Category deleted",
  )
}

export async function saveCollection(_: unknown, form: FormData) {
  const id = str(form, "id")
  const body = {
    name: str(form, "name"),
    slug: opt(form, "slug"),
    description: opt(form, "description"),
    image_url: opt(form, "image_url"),
    sort_order: Number(str(form, "sort_order") || 0),
    is_active: form.get("is_active") === "on",
    seo_title: opt(form, "seo_title"),
    seo_description: opt(form, "seo_description"),
  }
  return write(
    (c) =>
      (id
        ? c.PATCH("/api/v1/admin/collections/{collection_id}", { params: { path: { collection_id: id } }, body })
        : c.POST("/api/v1/admin/collections", { body })
      ).then(unwrap),
    ["collections", "catalog"],
    "Collection saved",
  )
}

export async function deleteCollection(id: string) {
  return write(
    (c) => c.DELETE("/api/v1/admin/collections/{collection_id}", { params: { path: { collection_id: id } } }).then(unwrap),
    ["collections", "catalog"],
    "Collection deleted",
  )
}

export async function createAttribute(_: unknown, form: FormData) {
  return write(
    (c) =>
      c
        .POST("/api/v1/admin/attributes", {
          body: {
            code: str(form, "code"),
            name: str(form, "name"),
            sort_order: Number(str(form, "sort_order") || 0),
            values: str(form, "values").split(",").map((v) => v.trim()).filter(Boolean),
          },
        })
        .then(unwrap),
    ["attributes"],
    "Option created",
  )
}

export async function importProducts(_: unknown, form: FormData) {
  return action(async () => {
    const dryRun = form.get("dry_run") === "on"
    const file = form.get("file")
    if (!(file instanceof File) || !file.size) throw new Error("Choose a CSV file")
    const body = new FormData()
    body.set("file", file)
    const report = await apiUpload<Record<string, unknown>>("/api/v1/admin/products/import", body, {
      dry_run: String(dryRun),
    })
    if (!dryRun) {
      revalidateTag("catalog", "max")
      refresh()
    }
    return report
  })
}

// ---------- Inventory ----------

export async function adjustStock(_: unknown, form: FormData) {
  const mode = str(form, "mode")
  const amount = Number(str(form, "amount"))
  return write(
    (c) =>
      c
        .POST("/api/v1/admin/inventory/{variant_id}/adjust", {
          params: { path: { variant_id: str(form, "variant_id") } },
          body: {
            reason: str(form, "reason"),
            ...(mode === "set" ? { set_to: amount } : { delta: amount }),
            low_stock_threshold: str(form, "low_stock_threshold") ? Number(str(form, "low_stock_threshold")) : null,
          },
        })
        .then(unwrap),
    ["products"],
    "Stock updated",
  )
}

// ---------- Orders ----------

export async function startProcessing(orderId: string) {
  return write(
    (c) => c.POST("/api/v1/admin/orders/{order_id}/process", { params: { path: { order_id: orderId } } }).then(unwrap),
    [],
    "Marked as processing",
  )
}

export async function createShipment(orderId: string) {
  return write(
    (c) => c.POST("/api/v1/admin/orders/{order_id}/shipments", { params: { path: { order_id: orderId } } }).then(unwrap),
    [],
    "Courier booked",
  )
}

export async function retryAwb(shipmentId: string) {
  return write(
    (c) => c.POST("/api/v1/admin/shipments/{shipment_id}/awb", { params: { path: { shipment_id: shipmentId } } }).then(unwrap),
    [],
    "AWB assigned",
  )
}

export async function syncTracking(shipmentId: string) {
  return write(
    (c) => c.POST("/api/v1/admin/shipments/{shipment_id}/sync", { params: { path: { shipment_id: shipmentId } } }).then(unwrap),
    [],
    "Tracking refreshed",
  )
}

export async function cancelOrderAdmin(_: unknown, form: FormData) {
  return write(
    (c) =>
      c
        .POST("/api/v1/admin/orders/{order_id}/cancel", {
          params: { path: { order_id: str(form, "order_id") } },
          body: { reason: str(form, "reason"), restock: form.get("restock") === "on" },
        })
        .then(unwrap),
    ["products"],
    "Order cancelled",
  )
}

export async function refundOrder(_: unknown, form: FormData) {
  const amount = toPaise(form.get("amount"))
  return write(
    (c) =>
      c
        .POST("/api/v1/admin/orders/{order_id}/refunds", {
          params: {
            path: { order_id: str(form, "order_id") },
            // One key per form submission: a double click can't refund twice.
            header: { "Idempotency-Key": str(form, "idempotency_key") || randomUUID() },
          },
          body: { reason: str(form, "reason"), amount_paise: amount },
        })
        .then(unwrap),
    [],
    "Refund initiated",
  )
}

export async function moderateReturn(returnId: string, decision: "approve" | "reject" | "receive", note?: string, restock = true) {
  return write(
    async (c) => {
      const params = { path: { return_id: returnId } }
      if (decision === "approve") return unwrap(await c.POST("/api/v1/admin/returns/{return_id}/approve", { params, body: { schedule_pickup: true, note: note || null } }))
      if (decision === "reject") return unwrap(await c.POST("/api/v1/admin/returns/{return_id}/reject", { params, body: { note: note || "Rejected" } }))
      return unwrap(await c.POST("/api/v1/admin/returns/{return_id}/receive", { params, body: { restock, note: note || null } }))
    },
    ["products"],
    decision === "receive" ? "Return received and refunded" : `Return ${decision}d`,
  )
}

// ---------- Customers & staff ----------

export async function setCustomerActive(userId: string, isActive: boolean, reason: string) {
  return write(
    (c) =>
      c
        .PATCH("/api/v1/admin/customers/{user_id}", {
          params: { path: { user_id: userId } },
          body: { is_active: isActive, reason },
        })
        .then(unwrap),
    [],
    isActive ? "Customer reactivated" : "Customer deactivated and signed out",
  )
}

export async function setRoles(userId: string, roles: S["RolesIn"]["roles"]) {
  return write(
    (c) => c.PUT("/api/v1/admin/users/{user_id}/roles", { params: { path: { user_id: userId } }, body: { roles } }).then(unwrap),
    [],
    "Roles updated",
  )
}

// ---------- Marketing ----------

export async function createCoupon(_: unknown, form: FormData) {
  const type = str(form, "discount_type") as "PERCENT" | "FIXED"
  const value = type === "PERCENT" ? Number(str(form, "value")) : toPaise(form.get("value")) ?? 0
  const date = (k: string) => (str(form, k) ? new Date(str(form, k)).toISOString() : null)
  return write(
    (c) =>
      c
        .POST("/api/v1/admin/coupons", {
          body: {
            code: str(form, "code"),
            description: opt(form, "description"),
            discount_type: type,
            value,
            max_discount_paise: toPaise(form.get("max_discount")),
            min_subtotal_paise: toPaise(form.get("min_subtotal")) ?? 0,
            usage_limit: str(form, "usage_limit") ? Number(str(form, "usage_limit")) : null,
            per_user_limit: str(form, "per_user_limit") ? Number(str(form, "per_user_limit")) : null,
            first_order_only: form.get("first_order_only") === "on",
            is_active: true,
            starts_at: date("starts_at"),
            ends_at: date("ends_at"),
          },
        })
        .then(unwrap),
    [],
    "Coupon created",
  )
}

export async function setCouponActive(id: string, isActive: boolean) {
  return write(
    (c) =>
      c.PATCH("/api/v1/admin/coupons/{coupon_id}", { params: { path: { coupon_id: id } }, body: { is_active: isActive } }).then(unwrap),
    [],
    isActive ? "Coupon enabled" : "Coupon disabled",
  )
}

export async function saveBanner(_: unknown, form: FormData) {
  const id = str(form, "id")
  const date = (k: string) => (str(form, k) ? new Date(str(form, k)).toISOString() : null)
  const body = {
    title: str(form, "title"),
    subtitle: opt(form, "subtitle"),
    image_url: str(form, "image_url"),
    link_url: opt(form, "link_url"),
    placement: str(form, "placement") as S["BannerIn"]["placement"],
    sort_order: Number(str(form, "sort_order") || 0),
    starts_at: date("starts_at"),
    ends_at: date("ends_at"),
    is_active: form.get("is_active") === "on",
  }
  return write(
    (c) =>
      (id
        ? c.PUT("/api/v1/admin/banners/{banner_id}", { params: { path: { banner_id: id } }, body })
        : c.POST("/api/v1/admin/banners", { body })
      ).then(unwrap),
    ["banners"],
    "Banner saved",
  )
}

export async function deleteBanner(id: string) {
  return write(
    (c) => c.DELETE("/api/v1/admin/banners/{banner_id}", { params: { path: { banner_id: id } } }).then(unwrap),
    ["banners"],
    "Banner deleted",
  )
}

// ---------- Reviews & notifications ----------

export async function moderateReview(id: string, decision: "approve" | "reject", note?: string) {
  return write(
    (c) =>
      (decision === "approve"
        ? c.POST("/api/v1/admin/reviews/{review_id}/approve", { params: { path: { review_id: id } }, body: { note: note || null } })
        : c.POST("/api/v1/admin/reviews/{review_id}/reject", { params: { path: { review_id: id } }, body: { note: note || null } })
      ).then(unwrap),
    ["reviews", "products"],
    decision === "approve" ? "Review published" : "Review rejected",
  )
}

export async function retryNotification(id: string) {
  return write(
    (c) => c.POST("/api/v1/admin/notifications/{notification_id}/retry", { params: { path: { notification_id: id } } }).then(unwrap),
    [],
    "Queued for retry",
  )
}

export async function saveTemplate(_: unknown, form: FormData) {
  return write(
    (c) =>
      c
        .PUT("/api/v1/admin/notification-templates/{code}", {
          params: { path: { code: str(form, "code") } },
          body: { subject: str(form, "subject"), body: String(form.get("body") ?? ""), is_active: true },
        })
        .then(unwrap),
    [],
    "Template saved",
  )
}

export async function resetTemplate(code: string) {
  return write(
    (c) => c.DELETE("/api/v1/admin/notification-templates/{code}", { params: { path: { code } } }).then(unwrap),
    [],
    "Template reset to default",
  )
}
