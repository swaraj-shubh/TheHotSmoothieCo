"use server"

import { refresh } from "next/cache"
import { redirect } from "next/navigation"

import { action, type ActionResult } from "@/lib/action-result"
import { api, unwrap } from "@/lib/api/client"
import { getCurrentUser } from "@/lib/session"

async function requireLogin(next: string) {
  if (!(await getCurrentUser())) redirect(`/login?next=${encodeURIComponent(next)}`)
}

/** The heart button: saves or un-saves a product. Guests are sent to sign in first.
 *  ponytail: looks through the first 100 saved items; paginate if wishlists ever outgrow that. */
export async function toggleWishlist(productId: string, returnTo: string): Promise<ActionResult<{ saved: boolean }>> {
  await requireLogin(returnTo)
  return action(async () => {
    const client = await api()
    const page = unwrap(await client.GET("/api/v1/wishlist", { params: { query: { limit: 100 } } }))
    const hit = page.items.find((i) => i.product.id === productId)
    if (hit) unwrap(await client.DELETE("/api/v1/wishlist/{item_id}", { params: { path: { item_id: hit.id } } }))
    else unwrap(await client.POST("/api/v1/wishlist", { body: { product_id: productId, variant_id: null } }))
    refresh()
    return { saved: !hit }
  })
}

/** Reviews are written from delivered orders and appear after moderation (which refreshes the
 *  product's review cache), so there is nothing to revalidate here. */
export async function submitReview(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  await requireLogin("/account/orders")
  return action(async () => {
    unwrap(
      await (await api()).POST("/api/v1/reviews", {
        body: {
          product_id: String(form.get("product_id") ?? ""),
          rating: Number(form.get("rating") ?? 0),
          title: String(form.get("title") ?? "").trim() || null,
          body: String(form.get("body") ?? "").trim() || null,
        },
      }),
    )
  }, "Thanks! Your review will appear once it's approved.")
}
