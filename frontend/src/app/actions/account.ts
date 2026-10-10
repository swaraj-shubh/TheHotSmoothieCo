"use server"

import { refresh } from "next/cache"

import { action, type ActionResult } from "@/lib/action-result"
import { api, unwrap } from "@/lib/api/client"
import type { AddressIn, AddressOut, OrderOut } from "@/lib/api/types"

function addressFromForm(form: FormData): AddressIn {
  const s = (k: string) => String(form.get(k) ?? "").trim()
  return {
    full_name: s("full_name"),
    phone: s("phone"),
    line1: s("line1"),
    line2: s("line2") || null,
    landmark: s("landmark") || null,
    city: s("city"),
    state: s("state"),
    postal_code: s("postal_code"),
    country: "IN",
    is_default_shipping: form.get("is_default_shipping") === "on",
    is_default_billing: form.get("is_default_billing") === "on",
  }
}

export async function saveAddress(_: ActionResult<AddressOut> | null, form: FormData): Promise<ActionResult<AddressOut>> {
  const id = String(form.get("id") ?? "")
  return action(async () => {
    const client = await api()
    const body = addressFromForm(form)
    const address = unwrap(
      id
        ? await client.PUT("/api/v1/users/me/addresses/{address_id}", { params: { path: { address_id: id } }, body })
        : await client.POST("/api/v1/users/me/addresses", { body }),
    )
    refresh()
    return address
  }, "Address saved")
}

export async function deleteAddress(id: string): Promise<ActionResult> {
  return action(async () => {
    unwrap(await (await api()).DELETE("/api/v1/users/me/addresses/{address_id}", { params: { path: { address_id: id } } }))
    refresh()
  })
}

export async function updateProfile(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  return action(async () => {
    unwrap(
      await (await api()).PATCH("/api/v1/users/me", {
        body: {
          full_name: String(form.get("full_name") ?? "").trim(),
          phone: String(form.get("phone") ?? "").trim() || null,
          preferences: { marketing_emails: form.get("marketing_emails") === "on" },
        },
      }),
    )
    refresh()
  }, "Profile updated")
}

export async function cancelOrder(orderId: string): Promise<ActionResult<OrderOut>> {
  return action(async () => {
    const order = unwrap(
      await (await api()).POST("/api/v1/orders/{order_id}/cancel", { params: { path: { order_id: orderId } } }),
    )
    refresh()
    return order
  }, "Order cancelled. Any payment will be refunded to your original payment method.")
}

export async function requestReturn(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  const orderId = String(form.get("order_id") ?? "")
  return action(async () => {
    unwrap(
      await (await api()).POST("/api/v1/orders/{order_id}/return", {
        params: { path: { order_id: orderId } },
        body: { reason: String(form.get("reason") ?? "").trim() },
      }),
    )
    refresh()
  }, "Return requested. We'll be in touch about pickup.")
}
