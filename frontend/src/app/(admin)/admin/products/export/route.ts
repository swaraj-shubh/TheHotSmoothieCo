import { cookies } from "next/headers"

import { API_URL, COOKIE } from "@/lib/api/client"

/** Streams the catalog CSV from the API with the staff member's credentials (the API checks
 *  the PRODUCT_MANAGER/ADMIN role). Nothing is buffered here. */
export async function GET() {
  const token = (await cookies()).get(COOKIE.access)?.value
  if (!token) return new Response("Sign in required", { status: 401 })
  const upstream = await fetch(`${API_URL}/api/v1/admin/products/export.csv`, {
    headers: {
      Authorization: `Bearer ${token}`,
      ...(process.env.BFF_SECRET ? { "X-BFF-Secret": process.env.BFF_SECRET } : {}),
    },
    cache: "no-store",
  })
  if (!upstream.ok || !upstream.body) return new Response("Export failed", { status: upstream.status })
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": upstream.headers.get("content-disposition") ?? 'attachment; filename="products.csv"',
      "Cache-Control": "no-store",
    },
  })
}
