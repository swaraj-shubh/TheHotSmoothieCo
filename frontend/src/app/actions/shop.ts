"use server"

import { refresh, revalidateTag } from "next/cache"
import { redirect } from "next/navigation"

import { action, type ActionResult } from "@/lib/action-result"
import { api, unwrap } from "@/lib/api/client"
import type { CartOut } from "@/lib/api/types"
import { getCurrentUser } from "@/lib/session"

async function requireLogin(next: string) {
  if (!(await getCurrentUser())) redirect(`/login?next=${encodeURIComponent(next)}`)
}

export async function addToWishlist(productId: string, variantId: string | null, returnTo: string): Promise<ActionResult> {
  await requireLogin(returnTo)
  return action(async () => {
    unwrap(await (await api()).POST("/api/v1/wishlist", { body: { product_id: productId, variant_id: variantId } }))
  }, "Saved to your wishlist")
}

export async function removeFromWishlist(itemId: string): Promise<ActionResult> {
  return action(async () => {
    unwrap(await (await api()).DELETE("/api/v1/wishlist/{item_id}", { params: { path: { item_id: itemId } } }))
    refresh()
  })
}

export async function moveWishlistToCart(itemId: string, variantId: string | null): Promise<ActionResult<CartOut>> {
  return action(async () => {
    const cart = unwrap(
      await (await api()).POST("/api/v1/wishlist/{item_id}/move-to-cart", {
        params: { path: { item_id: itemId } },
        body: { variant_id: variantId, quantity: 1 },
      }),
    )
    refresh()
    return cart
  }, "Moved to your cart")
}

export async function submitReview(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  const slug = String(form.get("slug") ?? "")
  await requireLogin(`/product/${slug}#reviews`)
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
    revalidateTag(`reviews:${slug}`, "max")
  }, "Thanks! Your review will appear once it's approved.")
}
