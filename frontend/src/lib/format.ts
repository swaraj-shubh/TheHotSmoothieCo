/** Indian-format rupees from integer paise: 12345678 -> "₹1,23,456.78" (".00" dropped by default). */
export function rupees(paise: number | null | undefined, { decimals = false } = {}): string {
  if (paise == null) return ""
  const value = paise / 100
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: decimals || value % 1 !== 0 ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(value)
}

/** The storefront's price format: 49900 -> "Rs. 499". */
export function money(paise: number | null | undefined): string {
  return "Rs. " + ((paise ?? 0) / 100).toLocaleString("en-IN")
}

/** Cloudinary delivery URL resized for display, never cropped (other hosts pass through unchanged). */
export function cdn(url: string, width: number): string {
  return url
    .replace(/\/image\/upload\/c_fill,w_\d+,h_\d+,q_auto,f_auto\//, "/image/upload/") // the API's square thumbnails
    .replace(/\/image\/upload\/(?!f_auto)/, `/image/upload/f_auto,q_auto,c_limit,w_${width}/`)
}

/** A cart or order line's size, falling back to the variant's name. */
export const sizeOf = (item: { attributes: Record<string, unknown>; variant_title: string }) =>
  (item.attributes.size as string | undefined) ?? item.variant_title

export function percentOff(price: number, compareAt: number | null | undefined): number | null {
  if (!compareAt || compareAt <= price) return null
  return Math.round(((compareAt - price) / compareAt) * 100)
}

const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" })
const dateTimeFmt = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  hour: "numeric",
  minute: "2-digit",
})

export const formatDate = (iso: string) => dateFmt.format(new Date(iso))
export const formatDateTime = (iso: string) => dateTimeFmt.format(new Date(iso))

export function titleCase(status: string): string {
  return status
    .toLowerCase()
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ")
}

const ORDER_LABELS: Record<string, string> = {
  PENDING_PAYMENT: "Awaiting payment",
  PAYMENT_PROCESSING: "Payment processing",
  PROCESSING: "Being printed",
}
/** Customer-facing order status. */
export const orderLabel = (status: string) => ORDER_LABELS[status] ?? titleCase(status)

/** Rupee string from a form ("1,499.50") -> paise, or null if blank/invalid. */
export function toPaise(input: FormDataEntryValue | null): number | null {
  const s = String(input ?? "").replace(/[₹,\s]/g, "")
  if (!s) return null
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null
  const [whole, frac = ""] = s.split(".")
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"))
}
