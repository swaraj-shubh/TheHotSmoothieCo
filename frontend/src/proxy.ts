import { NextResponse, type NextRequest } from "next/server"

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000"
const ACCESS = "hsc_at"
const REFRESH = "hsc_rt"
const REFRESH_AHEAD_SECONDS = 60

function visitorIp(request: NextRequest): string | undefined {
  return request.headers.get("x-real-ip") ?? request.headers.get("x-forwarded-for")?.split(",")[0]?.trim()
}

function expiresSoon(jwt: string | undefined): boolean {
  if (!jwt) return true
  try {
    const payload = JSON.parse(atob(jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")))
    return typeof payload.exp !== "number" || payload.exp - Date.now() / 1000 < REFRESH_AHEAD_SECONDS
  } catch {
    return true
  }
}

/**
 * Keeps the session fresh *before* rendering: Server Components can read cookies but not set
 * them, so an expiring access token is refreshed here and the new cookies are applied to both the
 * incoming request (so this render sees them) and the response (so the browser stores them).
 * Parallel requests racing to refresh are fine: the API honours a just-rotated token for 30 s.
 * This is an optimisation, not a security boundary — every Server Function and the API itself
 * check authentication again.
 */
export async function proxy(request: NextRequest) {
  const refreshToken = request.cookies.get(REFRESH)?.value
  if (!refreshToken || !expiresSoon(request.cookies.get(ACCESS)?.value)) return NextResponse.next()

  let res: Response
  try {
    res = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(process.env.BFF_SECRET ? { "X-BFF-Secret": process.env.BFF_SECRET } : {}),
        ...(visitorIp(request) ? { "X-Client-IP": visitorIp(request)! } : {}),
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
      cache: "no-store",
    })
  } catch {
    return NextResponse.next() // API unreachable: render as a guest this time, keep the cookies
  }

  const secure = process.env.NODE_ENV === "production"
  const opts = { httpOnly: true, secure, sameSite: "lax" as const, path: "/" }
  if (!res.ok) {
    if (res.status === 401) {
      request.cookies.delete(ACCESS)
      request.cookies.delete(REFRESH)
      const response = NextResponse.next({ request: { headers: request.headers } })
      response.cookies.delete(ACCESS)
      response.cookies.delete(REFRESH)
      return response
    }
    return NextResponse.next()
  }

  const tokens: { access_token: string; refresh_token: string | null; expires_in: number } = await res.json()
  request.cookies.set(ACCESS, tokens.access_token)
  const response = NextResponse.next({ request: { headers: request.headers } })
  response.cookies.set(ACCESS, tokens.access_token, { ...opts, maxAge: tokens.expires_in })
  if (tokens.refresh_token) {
    response.cookies.set(REFRESH, tokens.refresh_token, { ...opts, maxAge: 30 * 24 * 3600 })
  }
  return response
}

export const config = {
  // Pages and Server Functions only: never static assets or image optimisation.
  matcher: ["/((?!_next/static|_next/image|icon|apple-icon|opengraph-image|logo.png|robots.txt|sitemap.xml).*)"],
}
