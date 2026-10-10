"use client"

import { useActionState, useEffect, useState } from "react"
import { toast } from "sonner"

import { cancelOrderAdmin, createShipment, moderateReturn, refundOrder, retryAwb, startProcessing, syncTracking } from "@/app/actions/admin"
import { ActionButton } from "@/components/admin/action-button"
import { Field, FormMessage, SubmitButton } from "@/components/forms"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import type { AdminOrderOut } from "@/lib/api/types"
import { rupees } from "@/lib/format"

function useCloseOnSuccess(state: { ok: boolean; message?: string } | null, close: () => void) {
  useEffect(() => {
    if (state?.ok) {
      toast.success(state.message)
      close()
    }
  }, [state, close])
}

function CancelDialog({ order }: { order: AdminOrderOut }) {
  const [open, setOpen] = useState(false)
  const [state, action] = useActionState(cancelOrderAdmin, null)
  useCloseOnSuccess(state, () => setOpen(false))
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive">Cancel order</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Cancel {order.number}?</DialogTitle>
          <DialogDescription>
            {order.status === "PENDING_PAYMENT"
              ? "The held stock is released."
              : "Any courier booking is cancelled and the customer is refunded in full automatically."}
          </DialogDescription>
        </DialogHeader>
        <form action={action} className="space-y-4">
          <input type="hidden" name="order_id" value={order.id} />
          <Field label="Reason (sent to the audit log)" name="reason" required minLength={3} state={state} />
          <label className="flex items-center gap-2 text-sm">
            <Checkbox name="restock" defaultChecked /> Put the items back in stock
          </label>
          <FormMessage state={state && !state.ok ? state : null} />
          <SubmitButton variant="destructive">Cancel order</SubmitButton>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function RefundDialog({ order, refundable }: { order: AdminOrderOut; refundable: number }) {
  const [open, setOpen] = useState(false)
  const [state, action] = useActionState(refundOrder, null)
  // A fresh key each time the dialog opens: resubmitting the same form can't refund twice.
  const [key, setKey] = useState("")
  useCloseOnSuccess(state, () => setOpen(false))
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (o) setKey(crypto.randomUUID())
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline">Refund</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Refund {order.number}</DialogTitle>
          <DialogDescription>Up to {rupees(refundable, { decimals: true })} can be refunded. Leave the amount blank for the full remainder.</DialogDescription>
        </DialogHeader>
        <form action={action} className="space-y-4">
          <input type="hidden" name="order_id" value={order.id} />
          <input type="hidden" name="idempotency_key" value={key} />
          <Field label="Amount (₹)" name="amount" inputMode="decimal" placeholder={(refundable / 100).toFixed(2)} state={state} />
          <Field label="Reason" name="reason" required minLength={3} placeholder="Damaged in transit" state={state} />
          <FormMessage state={state && !state.ok ? state : null} />
          <SubmitButton>Refund</SubmitButton>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function OrderActions({ order, canWrite }: { order: AdminOrderOut; canWrite: boolean }) {
  if (!canWrite) return <p className="text-sm text-muted-foreground">You can view this order; changes need the Order Manager role.</p>
  const s = order.status
  const activeShipment = order.shipments.find((x) => !x.is_return && x.status !== "CANCELLED")
  const captured = order.payment?.status === "CAPTURED" ? order.payment.amount_paise : 0
  const refunded = order.refunds.filter((r) => r.status !== "FAILED").reduce((sum, r) => sum + r.amount_paise, 0)
  const refundable = Math.max(captured - refunded, 0)
  const openReturn = order.returns.find((r) => r.status === "REQUESTED" || r.status === "APPROVED")

  return (
    <div className="flex flex-wrap gap-2">
      {s === "CONFIRMED" && <ActionButton run={() => startProcessing(order.id)}>Start processing</ActionButton>}
      {(s === "CONFIRMED" || s === "PROCESSING") && !activeShipment && (
        <ActionButton
          run={() => createShipment(order.id)}
          confirm={{ title: "Book the courier?", description: "Creates the shipment, assigns an AWB and generates the label.", action: "Book courier" }}
        >
          Book courier
        </ActionButton>
      )}
      {activeShipment?.status === "CREATED" && (
        <ActionButton variant="outline" run={() => retryAwb(activeShipment.id)}>
          Retry AWB
        </ActionButton>
      )}
      {activeShipment?.awb && (
        <ActionButton variant="outline" run={() => syncTracking(activeShipment.id)}>
          Refresh tracking
        </ActionButton>
      )}
      {["PENDING_PAYMENT", "CONFIRMED", "PROCESSING", "PACKED"].includes(s) && <CancelDialog order={order} />}
      {refundable > 0 && <RefundDialog order={order} refundable={refundable} />}
      {openReturn?.status === "REQUESTED" && (
        <>
          <ActionButton
            run={() => moderateReturn(openReturn.id, "approve")}
            confirm={{ title: "Approve return?", description: "A return pickup is booked with the courier.", action: "Approve" }}
          >
            Approve return
          </ActionButton>
          <ActionButton
            variant="outline"
            run={() => moderateReturn(openReturn.id, "reject", "Not eligible for return")}
            confirm={{ title: "Reject this return?", action: "Reject" }}
          >
            Reject return
          </ActionButton>
        </>
      )}
      {openReturn?.status === "APPROVED" && (
        <ActionButton
          run={() => moderateReturn(openReturn.id, "receive")}
          confirm={{ title: "Mark return received?", description: "Restocks the items and refunds the customer in full.", action: "Receive & refund" }}
        >
          Return received
        </ActionButton>
      )}
    </div>
  )
}
