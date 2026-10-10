"use client"

import { useRouter } from "next/navigation"
import { useActionState, useEffect, useState, useTransition } from "react"
import { toast } from "sonner"

import { cancelOrder, requestReturn } from "@/app/actions/account"
import { initiatePayment, paymentStatus } from "@/app/actions/checkout"
import { FormMessage, SubmitButton } from "@/components/forms"
import { PayButton } from "@/components/shop/payment"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import type { InitiateOut } from "@/lib/api/types"

/** After returning from the payment widget the webhook may land a moment later: poll briefly. */
export function AwaitPayment({ orderId }: { orderId: string }) {
  const router = useRouter()
  useEffect(() => {
    let tries = 0
    const id = setInterval(async () => {
      tries += 1
      const r = await paymentStatus(orderId)
      if ((r.ok && r.data?.order_status !== "PENDING_PAYMENT") || tries >= 10) {
        clearInterval(id)
        router.refresh()
      }
    }, 2000)
    return () => clearInterval(id)
  }, [orderId, router])
  return <p className="text-sm text-muted-foreground">Confirming your payment…</p>
}

export function PayNow({ orderId }: { orderId: string }) {
  const [payment, setPayment] = useState<InitiateOut | null>(null)
  const [pending, start] = useTransition()
  if (payment) return <PayButton payment={payment} />
  return (
    <Button
      disabled={pending}
      onClick={() =>
        start(async () => {
          const r = await initiatePayment(orderId)
          if (r.ok && r.data) setPayment(r.data)
          else if (!r.ok) toast.error(r.error)
        })
      }
    >
      Complete payment
    </Button>
  )
}

export function CancelOrder({ orderId, paid }: { orderId: string; paid: boolean }) {
  const [pending, start] = useTransition()
  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant="outline" disabled={pending}>
          Cancel order
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Cancel this order?</AlertDialogTitle>
          <AlertDialogDescription>
            {paid
              ? "You'll get a full refund to your original payment method within 5–7 working days."
              : "The items will be released and the order closed."}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep order</AlertDialogCancel>
          <AlertDialogAction
            onClick={() =>
              start(async () => {
                const r = await cancelOrder(orderId)
                if (r.ok) toast.success(r.message)
                else toast.error(r.error)
              })
            }
          >
            Yes, cancel
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}

export function ReturnForm({ orderId }: { orderId: string }) {
  const [state, action] = useActionState(requestReturn, null)
  const [open, setOpen] = useState(false)
  if (state?.ok) return <FormMessage state={state} />
  if (!open)
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        Request a return
      </Button>
    )
  return (
    <form action={action} className="w-full space-y-3 border p-4">
      <input type="hidden" name="order_id" value={orderId} />
      <label className="block space-y-1.5 text-sm">
        <span className="font-medium">What went wrong?</span>
        <Textarea name="reason" required minLength={3} maxLength={500} rows={3} />
      </label>
      <FormMessage state={state} />
      <div className="flex gap-2">
        <SubmitButton>Submit return request</SubmitButton>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
          Never mind
        </Button>
      </div>
    </form>
  )
}
