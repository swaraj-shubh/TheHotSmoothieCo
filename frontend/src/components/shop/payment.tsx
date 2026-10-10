"use client"

import { useRouter } from "next/navigation"
import Script from "next/script"
import { useState, useTransition } from "react"
import { toast } from "sonner"

import { simulatePayment, verifyPayment } from "@/app/actions/checkout"
import { Button } from "@/components/ui/button"
import type { InitiateOut } from "@/lib/api/types"
import { rupees } from "@/lib/format"

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
export function PayButton({ payment, label = "Pay now" }: { payment: InitiateOut; label?: string }) {
  const router = useRouter()
  const [pending, start] = useTransition()
  const [scriptReady, setScriptReady] = useState(false)
  const done = (status?: string) => router.push(`/account/orders/${payment.order_id}?placed=1${status ? `&status=${status}` : ""}`)

  if (payment.provider === "dev") {
    return (
      <div className="space-y-3 border-2 border-dashed border-amber-400 bg-amber-50 p-4 text-sm">
        <p>
          <strong>Test mode.</strong> No real payment provider is configured, so you can simulate the outcome.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={pending}
            onClick={() =>
              start(async () => {
                const r = await simulatePayment(payment.order_id, "success")
                if (r.ok) done(r.data?.order_status)
                else toast.error(r.error)
              })
            }
          >
            Simulate successful payment of {rupees(payment.amount_paise, { decimals: true })}
          </Button>
          <Button
            variant="outline"
            disabled={pending}
            onClick={() =>
              start(async () => {
                const r = await simulatePayment(payment.order_id, "failure")
                toast[r.ok ? "info" : "error"](r.ok ? "Payment declined (simulated). You can try again." : r.error)
              })
            }
          >
            Simulate a declined card
          </Button>
        </div>
      </div>
    )
  }

  function open() {
    if (!window.Razorpay) return toast.error("The payment window is still loading. Please try again.")
    const rzp = new window.Razorpay({
      key: payment.public_key,
      order_id: payment.provider_order_id,
      amount: payment.amount_paise,
      currency: payment.currency,
      name: "The Hot Smoothie Co.",
      description: `Order ${payment.order_number}`,
      prefill: { name: payment.prefill.name, email: payment.prefill.email, contact: payment.prefill.contact ?? "" },
      theme: { color: "#002bcf" },
      handler: (response: RazorpayResponse) =>
        start(async () => {
          const r = await verifyPayment(payment.order_id, response)
          if (r.ok) done(r.data?.order_status)
          // The webhook may still confirm it; the order page polls the status.
          else done()
        }),
      modal: { ondismiss: () => toast.info("Payment window closed. Your order is saved; you can pay from your orders page.") },
    })
    rzp.on("payment.failed", (r) => toast.error(r.error?.description ?? "Payment failed. Please try another method."))
    rzp.open()
  }

  return (
    <>
      <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" onReady={() => setScriptReady(true)} />
      <Button size="lg" className="h-11 w-full text-base" disabled={pending || !scriptReady} onClick={open}>
        {pending ? "Confirming payment…" : `${label} · ${rupees(payment.amount_paise, { decimals: true })}`}
      </Button>
    </>
  )
}
