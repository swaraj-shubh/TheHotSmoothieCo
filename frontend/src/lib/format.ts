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

/** Rupee string from a form ("1,499.50") -> paise, or null if blank/invalid. */
export function toPaise(input: FormDataEntryValue | null): number | null {
  const s = String(input ?? "").replace(/[₹,\s]/g, "")
  if (!s) return null
  if (!/^\d+(\.\d{1,2})?$/.test(s)) return null
  const [whole, frac = ""] = s.split(".")
  return Number(whole) * 100 + Number(frac.padEnd(2, "0"))
}
