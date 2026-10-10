"use server"

import { refresh } from "next/cache"
import { redirect } from "next/navigation"

import { action, type ActionResult } from "@/lib/action-result"
import { api, unwrap } from "@/lib/api/client"
import type { CartOut } from "@/lib/api/types"
import { getCurrentUser, setCartCookie } from "@/lib/session"

async function afterCartChange(cart: CartOut) {
  if (cart.cart_token) await setCartCookie(cart.cart_token) // first guest add creates the cart
  refresh() // re-render the header badge and cart views
}

export async function addToCart(variantId: string, quantity: number): Promise<ActionResult<CartOut>> {
  return action(async () => {
    const cart = unwrap(
      await (await api()).POST("/api/v1/cart/items", { body: { variant_id: variantId, quantity } }),
    )
    await afterCartChange(cart)
    return cart
  }, "Added to cart")
}

/** "Buy now": add, then straight to checkout (login first if needed). */
export async function buyNow(variantId: string, quantity: number): Promise<ActionResult<CartOut>> {
  const result = await addToCart(variantId, quantity)
  if (result.ok) redirect((await getCurrentUser()) ? "/checkout" : "/login?next=/checkout")
  return result
}

export async function updateCartItem(itemId: string, quantity: number): Promise<ActionResult<CartOut>> {
  return action(async () => {
    const cart = unwrap(
      await (await api()).PATCH("/api/v1/cart/items/{item_id}", {
        params: { path: { item_id: itemId } },
        body: { quantity },
      }),
    )
    await afterCartChange(cart)
    return cart
  })
}

export async function removeCartItem(itemId: string): Promise<ActionResult<CartOut>> {
  return action(async () => {
    const cart = unwrap(
      await (await api()).DELETE("/api/v1/cart/items/{item_id}", { params: { path: { item_id: itemId } } }),
    )
    await afterCartChange(cart)
    return cart
  })
}

export async function applyCoupon(_: ActionResult<CartOut> | null, form: FormData): Promise<ActionResult<CartOut>> {
  return action(async () => {
    const cart = unwrap(
      await (await api()).POST("/api/v1/cart/coupon", { body: { code: String(form.get("code") ?? "").trim() } }),
    )
    await afterCartChange(cart)
    return cart
  }, "Coupon applied")
}

export async function removeCoupon(): Promise<ActionResult<CartOut>> {
  return action(async () => {
    const cart = unwrap(await (await api()).DELETE("/api/v1/cart/coupon"))
    await afterCartChange(cart)
    return cart
  })
}
