"use server"

import { refresh } from "next/cache"

import { action, type ActionResult } from "@/lib/action-result"
import { api, ApiError, unwrap } from "@/lib/api/client"
import type { CartOut } from "@/lib/api/types"
import { setCartCookie } from "@/lib/session"

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

/** "Add to cart" on a product card: the design has no size picker there, so it adds the cheapest
 *  size in stock (A4 for posters). */
export async function quickAdd(slug: string): Promise<ActionResult<CartOut>> {
  return action(async () => {
    const client = await api()
    const product = unwrap(await client.GET("/api/v1/products/{slug}", { params: { path: { slug } } }))
    const variant = product.variants.filter((v) => v.in_stock).sort((a, b) => a.price_paise - b.price_paise)[0]
    if (!variant) throw new ApiError(409, "SOLD_OUT", "Sold out. The croc is sorry.")
    const cart = unwrap(await client.POST("/api/v1/cart/items", { body: { variant_id: variant.id, quantity: 1 } }))
    await afterCartChange(cart)
    return cart
  })
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
