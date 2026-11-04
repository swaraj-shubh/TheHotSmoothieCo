import type { OrderOut } from "@/lib/api/types"
import { sizeOf } from "@/lib/format"

import { MiniLine } from "./checkout"

export function Address({ order }: { order: OrderOut }) {
  const a = order.shipping_address as Record<string, string | null>
  return (
    <p>
      {a.full_name}
      <br />
      {[a.line1, a.line2, a.landmark].filter(Boolean).join(", ")}
      <br />
      {a.city}, {a.state} {a.postal_code}
    </p>
  )
}

export function OrderLines({ order }: { order: OrderOut }) {
  return (
    <>
      {order.items.map((i) => (
        <MiniLine key={i.id} image={i.image_url} title={i.product_title} detail={`${sizeOf(i)} × ${i.quantity}`} price={i.line_total_paise} />
      ))}
    </>
  )
}
