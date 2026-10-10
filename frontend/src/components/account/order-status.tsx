import { titleCase } from "@/lib/format"
import { cn } from "@/lib/utils"

// Dot colour only; the label stays ink.
const TONE: Record<string, string> = {
  PENDING_PAYMENT: "bg-amber-500",
  PAYMENT_PROCESSING: "bg-amber-500",
  CONFIRMED: "bg-foreground",
  PROCESSING: "bg-foreground",
  PACKED: "bg-foreground",
  SHIPPED: "bg-brand",
  OUT_FOR_DELIVERY: "bg-brand",
  DELIVERED: "bg-emerald-600",
  RETURN_REQUESTED: "bg-sale",
  RETURNED: "bg-sale",
  REFUND_PENDING: "bg-sale",
}

const CUSTOMER_LABEL: Record<string, string> = {
  PENDING_PAYMENT: "Awaiting payment",
  PAYMENT_PROCESSING: "Payment processing",
  CONFIRMED: "Confirmed",
  PROCESSING: "Being printed",
}

export function OrderStatusBadge({ status, className }: { status: string; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-xs whitespace-nowrap", className)}>
      <span className={cn("size-1.5 rounded-full", TONE[status] ?? "bg-muted-foreground")} aria-hidden />
      {CUSTOMER_LABEL[status] ?? titleCase(status)}
    </span>
  )
}
