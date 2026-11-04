"use client"

import { useRouter } from "next/navigation"
import Script from "next/script"
import { useState, useTransition } from "react"

import { simulatePayment, verifyPayment } from "@/app/actions/checkout"
import type { InitiateOut } from "@/lib/api/types"
import { money } from "@/lib/format"

import { toast } from "./toast"

type RazorpayResponse = { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }
type RazorpayInstance = { open: () => void; on: (event: string, cb: (r: { error?: { description?: string } }) => void) => void }
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => RazorpayInstance
  }
}

/** Opens the payment provider for an order. Payment success is never trusted from the browser:
 *  the server verifies the signature, re-fetches the payment from Razorpay, and the webhook
 *  confirms independently. */
export function PayButton({ payment, method, label = "Pay" }: { payment: InitiateOut; method?: "upi"; label?: string }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [scriptReady, setScriptReady] = useState(false)
  const done = () => router.push(`/order-confirmed/${payment.order_id}`)

  if (payment.provider === "dev") {
    return (
      <div className="notice" style={{ display: "grid", gap: 16 }}>
        <p className="t-cap">
          <b>Test mode.</b> No real payment provider is configured, so you can simulate the outcome.
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          <button
            className="btn"
            disabled={pending}
            onClick={() =>
              start(async () => {
                const r = await simulatePayment(payment.order_id, "success")
                if (r.ok) done()
                else toast(r.error)
              })
            }
          >
            [ Simulate successful payment of {money(payment.amount_paise)} ]
          </button>
          <button
            className="btn btn--outline"
            disabled={pending}
            onClick={() =>
              start(async () => {
                const r = await simulatePayment(payment.order_id, "failure")
                toast(r.ok ? "Payment declined (simulated). You can try again." : r.error)
              })
            }
          >
            [ Simulate a declined card ]
          </button>
        </div>
      </div>
    )
  }

  function open() {
    if (!window.Razorpay) return toast("The payment window is still loading. Please try again.")
    const rzp = new window.Razorpay({
      key: payment.public_key,
      order_id: payment.provider_order_id,
      amount: payment.amount_paise,
      currency: payment.currency,
      name: "The Hot Smoothie Co.",
      description: `Order ${payment.order_number}`,
      prefill: { name: payment.prefill.name, email: payment.prefill.email, contact: payment.prefill.contact ?? "", ...(method ? { method } : {}) },
      theme: { color: "#c8261e" },
      handler: (response: RazorpayResponse) =>
        start(async () => {
          // Either way: if the webhook hasn't confirmed it yet, the next page waits for it.
          await verifyPayment(payment.order_id, response)
          done()
        }),
      modal: { ondismiss: () => toast("Payment window closed. Your order is saved; you can pay from your orders page.") },
    })
    rzp.on("payment.failed", (r) => toast(r.error?.description ?? "Payment failed. Please try another method."))
    rzp.open()
  }

  return (
    <>
      <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" onReady={() => setScriptReady(true)} />
      <button className="btn btn--block" style={{ padding: 18 }} disabled={pending || !scriptReady} onClick={open}>
        {pending ? "[ Confirming payment ]" : `[ ${label} ${money(payment.amount_paise)} ]`}
      </button>
    </>
  )
}
