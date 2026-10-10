import { NextResponse, type NextRequest } from "next/server"

import { publicApi } from "@/lib/api/client"

/** Search-as-you-type for the header search box. */
export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get("q")?.trim().slice(0, 100) ?? ""
  if (q.length < 2) return NextResponse.json([])
  const { data } = await publicApi.GET("/api/v1/search/suggest", { params: { query: { q, limit: 6 } } })
  return NextResponse.json(data ?? [], { headers: { "Cache-Control": "public, max-age=60" } })
}
