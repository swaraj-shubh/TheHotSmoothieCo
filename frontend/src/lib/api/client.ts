import "server-only"

import createClient from "openapi-fetch"
import { cookies, headers as requestHeaders } from "next/headers"
import { connection } from "next/server"

import type { paths } from "./schema"
import type { ApiErrorBody } from "./types"

/** Backend base URL. Server-side only: the browser never talks to the API directly (BFF). */
export const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000"

export const COOKIE = {
  access: "hsc_at",
  refresh: "hsc_rt",
  cart: "hsc_cart",
} as const

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message)
  }
}

// Proves to the API that a request comes from this server, so it may forward visitors' IPs.
const BFF_HEADERS: Record<string, string> = process.env.BFF_SECRET ? { "X-BFF-Secret": process.env.BFF_SECRET } : {}

/** Anonymous client: safe inside `'use cache'` (reads no request data). */
export const publicApi = createClient<paths>({ baseUrl: API_URL, headers: BFF_HEADERS })

/** The visitor's IP. On Vercel (or behind our own proxy) these headers are set by the platform. */
export async function visitorIp(): Promise<string | undefined> {
  const h = await requestHeaders()
  return h.get("x-real-ip") ?? h.get("x-forwarded-for")?.split(",")[0]?.trim() ?? undefined
}

/** Client for the current visitor: bearer token + guest cart token from httpOnly cookies.
 *  Reads cookies, so it must never be called inside a `'use cache'` scope. */
async function visitorHeaders(): Promise<Record<string, string>> {
  const jar = await cookies()
  const headers: Record<string, string> = { ...BFF_HEADERS }
  const ip = await visitorIp()
  if (ip) headers["X-Client-IP"] = ip
  const access = jar.get(COOKIE.access)?.value
  const cart = jar.get(COOKIE.cart)?.value
  if (access) headers.Authorization = `Bearer ${access}`
  if (cart) headers["X-Cart-Token"] = cart
  return headers
}

/** Multipart uploads (images, CSV): openapi-fetch's typed bodies are JSON-shaped, so these go
 *  through plain fetch with the same visitor headers. Throws ApiError like unwrap(). */
export async function apiUpload<T>(path: string, form: FormData, query?: Record<string, string>): Promise<T> {
  await connection()
  const url = new URL(path, API_URL)
  for (const [k, v] of Object.entries(query ?? {})) url.searchParams.set(k, v)
  const response = await fetch(url, { method: "POST", body: form, headers: await visitorHeaders(), cache: "no-store" })
  const data = await response.json().catch(() => undefined)
  return unwrap<T>({ data: response.ok ? data : undefined, error: response.ok ? undefined : data, response })
}

export async function api() {
  // Per-visitor, uncached API calls only make sense at request time: opt out of (runtime)
  // prerendering explicitly so nothing below runs during a prefetch render.
  await connection()
  return createClient<paths>({ baseUrl: API_URL, headers: await visitorHeaders(), cache: "no-store" })
}

/** Unwrap an openapi-fetch result: return data or throw a typed ApiError. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.error !== undefined || !res.response.ok) {
    const body = res.error as ApiErrorBody | undefined
    throw new ApiError(
      res.response.status,
      body?.error?.code ?? "HTTP_ERROR",
      body?.error?.message ?? res.response.statusText,
      body?.error?.details,
    )
  }
  return res.data as T
}

/** Same as unwrap, but 404 -> null (for "maybe it exists" reads). */
export function unwrapOrNull<T>(res: { data?: T; error?: unknown; response: Response }): T | null {
  if (res.response.status === 404) return null
  return unwrap(res)
}
