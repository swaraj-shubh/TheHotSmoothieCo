"use server"

import { refresh } from "next/cache"

import { action, type ActionResult } from "@/lib/action-result"
import { api, unwrap } from "@/lib/api/client"
import type { InitiateOut, OrderOut } from "@/lib/api/types"

export type PlacedOrder = { order: OrderOut; payment: InitiateOut }

/** Cart -> PENDING_PAYMENT order (stock held) -> gateway order for the payment widget.
 *  `idempotencyKey` is generated once per checkout visit, so retries/double clicks return the
 *  same order instead of creating a second one. */
export async function placeOrder(input: {
  addressId: string
  expectedTotalPaise: number
  idempotencyKey: string
  notes?: string
}): Promise<ActionResult<PlacedOrder>> {
  return action(async () => {
    const client = await api()
    const order = unwrap(
      await client.POST("/api/v1/checkout", {
        params: { header: { "Idempotency-Key": input.idempotencyKey } },
        body: {
          shipping_address_id: input.addressId,
          expected_total_paise: input.expectedTotalPaise,
          notes: input.notes || null,
        },
      }),
    )
    const payment = unwrap(
      await client.POST("/api/v1/payments/orders/{order_id}/initiate", { params: { path: { order_id: order.id } } }),
    )
    return { order, payment }
  })
}

/** Restart payment for an order that's still awaiting it (e.g. the customer closed the widget). */
export async function initiatePayment(orderId: string): Promise<ActionResult<InitiateOut>> {
  return action(async () =>
    unwrap(await (await api()).POST("/api/v1/payments/orders/{order_id}/initiate", { params: { path: { order_id: orderId } } })),
  )
}

export async function verifyPayment(
  orderId: string,
  razorpay: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string },
): Promise<ActionResult<{ order_status: string }>> {
  return action(async () => {
    const status = unwrap(
      await (await api()).POST("/api/v1/payments/orders/{order_id}/verify", {
        params: { path: { order_id: orderId } },
        body: {
          provider_order_id: razorpay.razorpay_order_id,
          provider_payment_id: razorpay.razorpay_payment_id,
          signature: razorpay.razorpay_signature,
        },
      }),
    )
    refresh()
    return { order_status: status.order_status }
  })
}

/** Development only (PAYMENTS_PROVIDER=dev on the API): complete or decline the payment. */
export async function simulatePayment(orderId: string, outcome: "success" | "failure"): Promise<ActionResult<{ order_status: string }>> {
  return action(async () => {
    const status = unwrap(
      await (await api()).POST("/api/v1/payments/orders/{order_id}/simulate", {
        params: { path: { order_id: orderId } },
        body: { outcome },
      }),
    )
    refresh()
    return { order_status: status.order_status }
  })
}

export async function paymentStatus(orderId: string): Promise<ActionResult<{ order_status: string; payment_status: string | null }>> {
  return action(async () => {
    const s = unwrap(await (await api()).GET("/api/v1/payments/orders/{order_id}", { params: { path: { order_id: orderId } } }))
    return { order_status: s.order_status, payment_status: s.payment_status ?? null }
  })
}
